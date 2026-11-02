"""Document loading (TXT / MD / PDF) and heading-based policy chunking."""
import json
import re
from pathlib import Path

from .schemas import CaseRequest, PolicyChunk

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_CHUNK_WORDS = 120


def read_document(path_or_bytes, filename: str = "") -> str:
    """Return plain text from a .txt/.md path, or a PDF path / uploaded PDF bytes."""
    name = filename or str(path_or_bytes)
    if name.lower().endswith(".pdf"):
        import fitz  # PyMuPDF, imported lazily so TXT-only use doesn't need it
        doc = (fitz.open(stream=path_or_bytes, filetype="pdf") if isinstance(path_or_bytes, bytes)
               else fitz.open(path_or_bytes))
        return "\n".join(page.get_text() for page in doc)
    if isinstance(path_or_bytes, bytes):
        return path_or_bytes.decode("utf-8", errors="replace")
    return Path(path_or_bytes).read_text(encoding="utf-8")


def load_cases(cases_dir: Path = DATA_DIR / "cases") -> list[tuple[CaseRequest, str]]:
    """Return (request, split) pairs from cases.json; split is 'dev' or 'heldout'."""
    rows = json.loads((cases_dir / "cases.json").read_text(encoding="utf-8"))
    out = []
    for row in rows:
        note = read_document(cases_dir / row.pop("note_file"))
        split = row.pop("split", "dev")
        out.append((CaseRequest(note_text=note, **row), split))
    return out


def chunk_markdown(text: str, document: str) -> list[PolicyChunk]:
    """Split on '## ' headings so every chunk carries a citable section name.

    Sections longer than MAX_CHUNK_WORDS are split further on paragraph boundaries.
    Text without headings (e.g. a PDF) becomes one 'Full document' section.
    """
    title = re.search(r"(?m)^# (.+)$", text)
    title = title.group(1).strip() if title else Path(document).stem.replace("_", " ")
    codes = re.search(r"(?mi)^Applies to procedure codes:\s*(.+)$", text)
    codes = [c.strip() for c in codes.group(1).split(",")] if codes else []
    blocks = re.split(r"(?m)^## ", text)[1:]  # [0] is the title/disclaimer
    sections = [b.partition("\n")[::2] for b in blocks] or [("Full document", text)]
    chunks = []
    for section, body in sections:
        paragraphs = [" ".join(p.split()) for p in body.split("\n\n") if p.strip()]
        groups, current = [], []
        for p in paragraphs:
            if current and len(" ".join(current + [p]).split()) > MAX_CHUNK_WORDS:
                groups.append(current)
                current = []
            current.append(p)
        if current:
            groups.append(current)
        slug = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")
        for i, group in enumerate(groups):
            chunks.append(PolicyChunk(chunk_id=f"{Path(document).stem}#{slug}-{i}",
                                      document=document, title=title, section=section.strip(),
                                      text=" ".join(group), procedure_codes=codes))
    return chunks


def load_policies(policies_dir: Path = DATA_DIR / "policies") -> list[PolicyChunk]:
    chunks = []
    for path in sorted(policies_dir.glob("*")):
        if path.suffix.lower() in {".md", ".txt", ".pdf"}:
            chunks += chunk_markdown(read_document(path), path.name)
    return chunks
