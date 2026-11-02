from streamlit.testing.v1 import AppTest

from src import ui
from src.ingestion import load_cases
from src.pipeline import build_index, review_case
from src.schemas import CaseRequest


def test_uploaded_note_is_escaped_and_cited_sentence_marked():
    req = CaseRequest(case_id="X", requested_procedure="Total knee arthroplasty", procedure_code="27447",
                      diagnosis="Osteoarthritis of the knee",
                      note_text="<script>alert(1)</script>\nAssessment: Osteoarthritis of the right knee.")
    html = ui.highlight_note(review_case(req, build_index("tfidf")))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert '<mark class="hl hl--ok" title="Cited by C1">Assessment: Osteoarthritis of the right knee.' in html


def test_app_renders_every_sample_case(monkeypatch):
    monkeypatch.setattr("src.pipeline.DEFAULT_BACKEND", "tfidf")
    at = AppTest.from_file("app.py", default_timeout=60).run()
    for req, _ in load_cases():
        at.selectbox[0].set_value(req.case_id).run()
        assert not at.exception, req.case_id
