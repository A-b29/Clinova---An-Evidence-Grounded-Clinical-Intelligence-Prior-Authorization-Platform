"""Clinova reviewer UI.  Run:  streamlit run app.py"""
import os
from pathlib import Path

import streamlit as st

from src import ui
from src.ingestion import load_cases, read_document
from src.pipeline import DEFAULT_BACKEND, build_index, review_case
from src.reporting import to_markdown
from src.schemas import FACT_FIELDS, CaseRequest

ASSETS = Path(__file__).parent / "assets"
REPO = "https://github.com/A-b29/Clinova---An-Evidence-Grounded-Clinical-Intelligence-Prior-Authorization-Platform"
SCENARIOS = {
    "PA-001": "Complete documentation: the happy path.",
    "PA-002": "Imaging and conservative treatment are missing from the note.",
    "PA-003": "The radiology report and the clinic summary disagree on severity.",
    "PA-004": "Complete documentation under a different policy (hip).",
    "PA-005": "Request and note disagree on the diagnosis; PT is both tried and declined.",
    "PA-006": "Held-out: clinical shorthand the rules weren't written for.",
    "PA-007": "Held-out: explicit negations (\"denies PT\", \"no imaging on file\").",
}

st.set_page_config(page_title="Clinova · Prior-authorization review", page_icon=str(ASSETS / "mark.svg"),
                   layout="wide")
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "mark.svg"), size="large")
st.html(ASSETS / "style.css")


@st.cache_resource(show_spinner="Loading policy index…")
def get_index():
    return build_index(DEFAULT_BACKEND)


def empty_state(title: str, body: str):
    st.html(f'<div class="empty-state"><h3>{title}</h3><p>{body}</p></div>')
    st.stop()


cases = {req.case_id: (req, split) for req, split in load_cases()}
index = get_index()
has_key = bool(os.getenv("ANTHROPIC_API_KEY"))

with st.sidebar:
    st.html('<div class="side-label">Case</div>')
    source = st.segmented_control("Input", ["Sample case", "Upload note"], default="Sample case", required=True,
                                  label_visibility="collapsed", width="stretch")
    if source == "Sample case":
        # bound to ?case=PA-003 so a demo link can open straight on a case
        case_id = st.selectbox("Synthetic case", list(cases), key="case", bind="query-params")
        request, split = cases[case_id]
    else:
        upload = st.file_uploader("Clinical note (.txt or .pdf)", type=["txt", "pdf"])
        case_id = st.text_input("Case ID", "PA-NEW")
        procedure = st.text_input("Requested procedure", "Total knee arthroplasty")
        procedure_code = st.text_input("Procedure code", "27447", help="Routes retrieval to the matching policy.")
        diagnosis = st.text_input("Request diagnosis", "Osteoarthritis of the knee")
        note = read_document(upload.getvalue(), upload.name) if upload else ""
        request = split = None
        if note.strip():
            request, split = CaseRequest(case_id=case_id, requested_procedure=procedure, diagnosis=diagnosis,
                                         procedure_code=procedure_code or None, note_text=note), "upload"

    st.html('<div class="side-label">Engine</div>')
    extractor = st.segmented_control(
        "Fact extractor", ["rules", "llm"], format_func={"rules": "Rules", "llm": "Claude"}.get, default="rules",
        required=True, disabled=not has_key, width="stretch",
        help="Claude needs ANTHROPIC_API_KEY. Use synthetic data only." if has_key else
             "Set ANTHROPIC_API_KEY to enable the Claude extractor.")
    st.caption(f"Retrieval: {index.backend} over {len(index.chunks)} policy passages, routed by CPT code.")
    st.html(f'<div class="side-foot">Every status links to the note sentence and policy section behind it. '
            f'Synthetic data only.<br><a href="{REPO}" target="_blank">Source on GitHub</a> · '
            f'<a href="{REPO}/blob/main/docs/MODEL_FLOW_AND_DECISIONS.md" target="_blank">How it works</a></div>')

st.html(ui.BANNER)
if request is None:
    empty_state("Upload a synthetic clinical note",
                "Add a .txt or .pdf note in the sidebar to start a review. Never upload real patient data.")

try:
    review = review_case(request, index, extractor)
except Exception as e:  # surface API / parsing failures instead of a blank page
    st.error(f"Review failed: {e}")
    st.stop()

head, actions = st.columns([4, 1], vertical_alignment="bottom")
head.html(ui.case_header(review, SCENARIOS.get(request.case_id, "") if split != "upload" else "", split))
report = to_markdown(review)
actions.download_button("Download report", report, f"{request.case_id}_review.md", "text/markdown",
                        type="primary", icon=":material/download:", width="stretch")
actions.download_button("Export JSON", review.model_dump_json(indent=2), f"{request.case_id}_review.json",
                        "application/json", icon=":material/data_object:", width="stretch")
st.html(ui.overview(review))

tab_review, tab_facts, tab_report = st.tabs(["Review", "Extracted facts", "Report preview"])

with tab_review:
    left, right = st.columns([3, 2], gap="medium")
    with left:
        for r in review.checklist:
            st.html(ui.criterion_card(r))
        st.caption(review.checklist[0].uncertainty)
    with right:
        st.html(ui.highlight_note(review))
        if review.follow_up_questions:
            st.html(ui.follow_ups(review.follow_up_questions))
            with st.expander("Copy as a message to the provider", icon=":material/content_copy:"):
                st.code("\n".join(review.follow_up_questions), language=None, wrap_lines=True)

with tab_facts:
    rows = [{"Fact type": field.replace("_", " ").capitalize(), "Value": f.value,
             "Assertion": "Negated" if f.negated else "Affirmed", "Evidence (verbatim from note)": f.evidence}
            for field in FACT_FIELDS for f in getattr(review.facts, field)]
    st.dataframe(rows, hide_index=True, column_config={
        "Evidence (verbatim from note)": st.column_config.TextColumn(width="large")})
    for m in review.facts.uncertain_or_missing:
        st.caption(f"• {m.replace('_', ' ').capitalize()}")
    with st.expander("Validated JSON", icon=":material/data_object:"):
        st.json(review.facts.model_dump())

with tab_report:
    with st.container(border=True):
        st.markdown(report)
