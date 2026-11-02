"""Streamlit reviewer UI.  Run:  streamlit run app.py"""
import os

import streamlit as st

from src.ingestion import load_cases, read_document
from src.pipeline import DEFAULT_BACKEND, build_index, review_case
from src.reporting import ICON, to_markdown
from src.schemas import FACT_FIELDS, CaseRequest

st.set_page_config(page_title="Prior-Auth Review Copilot", page_icon="🩺", layout="wide")


@st.cache_resource(show_spinner="Loading policy index…")
def get_index():
    return build_index(DEFAULT_BACKEND)


st.title("🩺 Clinical Claims Intelligence & Prior-Authorization Copilot")
st.warning("**Educational prototype.** Synthetic data and illustrative policies only. It does not approve or deny "
           "requests or give medical advice. Decision-support output only; human review required.")

cases = {req.case_id: req for req, _ in load_cases()}
with st.sidebar:
    st.header("Case")
    source = st.radio("Input", ["Sample case", "Upload a note"], horizontal=True)
    if source == "Sample case":
        request = cases[st.selectbox("Synthetic case", sorted(cases))]
    else:
        upload = st.file_uploader("Clinical note (.txt or .pdf)", type=["txt", "pdf"])
        case_id = st.text_input("Case ID", "PA-NEW")
        procedure = st.text_input("Requested procedure", "Total knee arthroplasty")
        procedure_code = st.text_input("Procedure code (routes to the matching policy)", "27447")
        diagnosis = st.text_input("Request diagnosis", "Osteoarthritis of the knee")
        note = read_document(upload.getvalue(), upload.name) if upload else ""
        if not note.strip():
            st.info("Upload a synthetic note to continue. Do not upload real patient data.")
            st.stop()
        request = CaseRequest(case_id=case_id, requested_procedure=procedure, procedure_code=procedure_code or None,
                              diagnosis=diagnosis, note_text=note)

    st.header("Models")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    extractor = st.radio("Fact extractor", ["rules", "llm"], horizontal=True, disabled=not has_key,
                         help="'llm' uses Claude and needs ANTHROPIC_API_KEY. Synthetic data only.")
    st.caption(f"Retriever: `{get_index().backend}` · LLM: {'available' if has_key else 'no API key set'}")

try:
    review = review_case(request, get_index(), extractor)
except Exception as e:  # surface API / parsing failures instead of a blank page
    st.error(f"Review failed: {e}")
    st.stop()

cols = st.columns(len(review.checklist))
for col, r in zip(cols, review.checklist):
    col.metric(f"{r.criterion_id}", f"{ICON[r.status]} {r.status}", help=r.criterion)

tab_note, tab_facts, tab_check, tab_report = st.tabs(
    ["📄 Clinical note", "🔎 Extracted facts", "✅ Criteria checklist", "📝 Review report"])

with tab_note:
    st.markdown(f"**{request.case_id}** · {request.requested_procedure} ({request.procedure_code or 'no code'}) · "
                f"request diagnosis: {request.diagnosis}")
    st.code(request.note_text, language=None)

with tab_facts:
    rows = [{"field": field, "value": f.value, "negated": f.negated, "evidence (verbatim from note)": f.evidence}
            for field in FACT_FIELDS for f in getattr(review.facts, field)]
    st.dataframe(rows, width="stretch", hide_index=True)
    if review.facts.uncertain_or_missing:
        st.markdown("**Uncertain or missing**\n" + "\n".join(f"- {m}" for m in review.facts.uncertain_or_missing))
    with st.expander("Validated JSON"):
        st.json(review.facts.model_dump())

with tab_check:
    for r in review.checklist:
        with st.container(border=True):
            st.markdown(f"#### {ICON[r.status]} {r.criterion_id}. {r.criterion}: `{r.status}`")
            st.write(r.explanation)
            st.caption(r.uncertainty)
            left, right = st.columns(2)
            left.markdown("**Clinical-note evidence**")
            for f in r.note_evidence:
                left.markdown(f"- {'~~' if f.negated else ''}`{f.value}`{'~~ (negated)' if f.negated else ''}: "
                              f"_{f.evidence}_")
            if not r.note_evidence:
                left.markdown("_None found in the submitted note._")
            right.markdown("**Retrieved policy passages**")
            for p in r.policy_passages:
                with right.expander(f"{p.document} § {p.section} (score {p.score:.2f})"):
                    st.write(p.text)

with tab_report:
    report = to_markdown(review)
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Report (.md)", report, f"{request.case_id}_review.md", "text/markdown")
    c2.download_button("⬇️ Full review (.json)", review.model_dump_json(indent=2), f"{request.case_id}_review.json",
                       "application/json")
    st.markdown(report)
