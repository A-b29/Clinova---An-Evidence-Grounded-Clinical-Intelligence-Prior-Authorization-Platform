"""Deterministic, citation-linked Markdown review report (no LLM: nothing to hallucinate)."""
from .schemas import FACT_FIELDS, Review

DISCLAIMER = "**Decision-support output only; human review required.**"
ICON = {"SUPPORTED": "✅", "NOT_FOUND": "⚪", "CONFLICTING": "⚠️"}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(review: Review) -> str:
    req, facts = review.request, review.facts
    lines = [
        f"# Prior-Authorization Review: {req.case_id}",
        "",
        DISCLAIMER + " Synthetic data and illustrative policies; not a coverage decision.",
        "",
        f"- **Requested procedure:** {req.requested_procedure}" + (f" (code {req.procedure_code})" if req.procedure_code else ""),
        f"- **Request diagnosis:** {req.diagnosis}" + (f" ({req.diagnosis_code})" if req.diagnosis_code else ""),
        f"- **Extractor / retriever:** {review.extractor} / {review.retriever}  ·  **Latency:** {review.latency_ms:.0f} ms",
        "",
        "## Criteria checklist",
        "",
        "| # | Criterion | Status | Explanation |",
        "|---|---|---|---|",
    ]
    lines += [f"| {r.criterion_id} | {_cell(r.criterion)} | {ICON[r.status]} {r.status} | {_cell(r.explanation)} |"
              for r in review.checklist]

    lines += ["", "## Evidence by criterion"]
    for r in review.checklist:
        lines += ["", f"### {r.criterion_id}. {r.criterion}: {r.status}", "", "**Clinical-note evidence**", ""]
        lines += [f"- {'(negated) ' if f.negated else ''}`{f.value}`: \"{f.evidence}\"" for f in r.note_evidence] \
            or ["- None found in the submitted note."]
        lines += ["", "**Retrieved policy passages**", ""]
        lines += [f"- [{p.document} § {p.section}] (score {p.score:.2f}): \"{p.text}\"" for p in r.policy_passages]

    lines += ["", "## Extracted clinical facts", ""]
    for field in FACT_FIELDS:
        values = [f"{f.value}{' (negated)' if f.negated else ''}" for f in getattr(facts, field)]
        lines.append(f"- **{field}:** {', '.join(dict.fromkeys(values)) or '—'}")

    gaps = [r for r in review.checklist if r.status != "SUPPORTED"]
    lines += ["", "## Missing or conflicting documentation", ""]
    lines += [f"- **{r.status}** {r.criterion_id} ({r.criterion}): {r.explanation}" for r in gaps] or ["- None identified."]
    lines += ["", "## Questions for human follow-up", ""]
    lines += [f"- {q}" for q in review.follow_up_questions] or ["- None."]
    lines += ["", "---", DISCLAIMER]
    return "\n".join(lines)
