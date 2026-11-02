import pytest

from src.ingestion import chunk_markdown, load_policies, read_document
from src.retrieval import PolicyIndex

CHUNKS = load_policies()
INDEX = PolicyIndex(CHUNKS, backend="tfidf")  # tfidf keeps tests fast and offline


def test_chunks_are_traceable():
    assert CHUNKS and all(c.document and c.section and c.text and "#" in c.chunk_id for c in CHUNKS)
    assert len({c.chunk_id for c in CHUNKS}) == len(CHUNKS)
    assert not any("ILLUSTRATIVE SAMPLE TEXT" in c.text for c in CHUNKS)  # title/disclaimer block skipped


def test_long_sections_split_and_headingless_text_kept():
    para = " ".join(["word"] * 80)
    chunks = chunk_markdown(f"# T\n\n## Long\n{para}\n\n{para}\n", "doc.md")
    assert [c.section for c in chunks] == ["Long", "Long"]
    [chunk] = chunk_markdown("plain text from a PDF", "doc.pdf")
    assert chunk.section == "Full document"


def test_pdf_upload_is_read():
    import fitz
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Knee pain for 2 years.")
    assert "Knee pain for 2 years." in read_document(doc.tobytes(), "note.pdf")


def test_routing_restricts_to_procedure_policy():
    hits = INDEX.search("imaging findings of the affected joint", k=5, procedure_code="27447")
    assert {h.document for h in hits} <= {"policy_total_knee_arthroplasty.md", "general_documentation_guidelines.md"}
    assert hits[0].section == "Criterion 2: Imaging findings"


def test_unknown_code_searches_everything():
    hits = INDEX.search("hip replacement imaging", k=3, procedure_code="00000")
    assert hits[0].document == "policy_total_hip_arthroplasty.md"


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        PolicyIndex(CHUNKS, backend="bm42")
