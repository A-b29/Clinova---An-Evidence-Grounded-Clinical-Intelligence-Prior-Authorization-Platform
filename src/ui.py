"""HTML fragments for the Streamlit UI. All note and policy text is escaped: uploaded notes are untrusted."""
import re
from collections import Counter
from html import escape

from .schemas import CriterionResult, Review

# status -> (label, css modifier); list order = severity, used when one sentence backs several criteria
STATUS = {"SUPPORTED": ("Supported", "ok"), "NOT_FOUND": ("Not found", "gap"), "CONFLICTING": ("Conflicting", "conflict")}
SEVERITY = list(STATUS)

BANNER = ('<div class="banner"><span><b>Decision support only.</b> Synthetic data and illustrative policies. '
          'Clinova never approves or denies a request; a human reviewer decides.</span></div>')


def chip(status: str) -> str:
    label, mod = STATUS[status]  # icon glyph comes from CSS (st.html strips inline SVG)
    return f'<span class="chip chip--{mod}">{label}</span>'


def short_name(r: CriterionResult) -> str:
    name = r.criterion.removeprefix("Documentation of ").removeprefix("the relevant ")
    return name[0].upper() + name[1:]


def case_header(review: Review, scenario: str, split: str) -> str:
    req = review.request
    tags = [f"CPT {req.procedure_code}" if req.procedure_code else "No procedure code",
            f"ICD-10 {req.diagnosis_code}" if req.diagnosis_code else None,
            {"dev": "Dev case", "heldout": "Held-out case"}.get(split, "Uploaded note")]
    tags_html = "".join(f'<span class="tag">{escape(t)}</span>' for t in tags if t)
    return (f'<div class="case"><div class="eyebrow">Prior-authorization review · {escape(req.case_id)}</div>'
            f'<h1>{escape(req.requested_procedure)}</h1>'
            f'<div class="tags">{tags_html}<span class="dx">Request diagnosis: {escape(req.diagnosis)}</span></div>'
            + (f'<p class="scenario">{escape(scenario)}</p>' if scenario else "") + '</div>')


def overview(review: Review) -> str:
    counts, n = Counter(r.status for r in review.checklist), len(review.checklist)
    conflicts, gaps, issues = counts["CONFLICTING"], counts["NOT_FOUND"], []
    if conflicts:
        issues.append(f"{conflicts} conflict{'s' if conflicts > 1 else ''} to resolve")
    if gaps:
        issues.append(f"{gaps} documentation gap{'s' if gaps > 1 else ''}")
    headline = "Needs reviewer attention" if issues else "Documentation complete"
    detail = " · ".join(issues) or f"All {n} criteria have supporting evidence in the note."
    tiles = "".join(f'<div class="tile tile--{STATUS[r.status][1]}"><span class="cid">{r.criterion_id}</span>'
                    f'<span class="tname">{escape(short_name(r))}</span>{chip(r.status)}</div>'
                    for r in review.checklist)
    return (f'<div class="overview"><div class="score"><div><div class="hero">{counts["SUPPORTED"]}<span>/{n}</span>'
            f'</div><div class="hero-label">supported</div></div>'
            f'<div><div class="headline">{headline}</div><div class="muted">{escape(detail)}</div>'
            f'<div class="meta">Reviewed in {review.latency_ms:.0f} ms · {escape(review.extractor)} extractor · '
            f'{escape(review.retriever)} retriever</div></div></div><div class="tiles">{tiles}</div></div>')


def criterion_card(r: CriterionResult) -> str:
    by_sentence = {}  # one quote per sentence, with every term it supports
    for f in r.note_evidence:
        by_sentence.setdefault(f.evidence, []).append(f)
    evidence = "".join(
        "<li>" + "".join(f'<span class="term">{escape(f.value)}</span>'
                         + ('<span class="neg">stated absent</span>' if f.negated else "") for f in facts)
        + f"<q>{escape(sentence)}</q></li>" for sentence, facts in by_sentence.items()
    ) or '<li class="empty">Nothing in the submitted note.</li>'
    policy = "".join(
        f'<details><summary><span class="doc">{escape(p.title.split(": ", 1)[-1])}</span>'
        f'<span class="sec">§ {escape(p.section)}</span><span class="match">match {p.score:.2f}</span></summary>'
        f'<p>{escape(p.text)}</p></details>' for p in r.policy_passages)
    return (f'<article class="crit crit--{STATUS[r.status][1]}"><header><span class="cid">{r.criterion_id}</span>'
            f'<h4>{escape(r.criterion)}</h4>{chip(r.status)}</header><p class="why">{escape(r.explanation)}</p>'
            f'<h5>Evidence from note</h5><ul class="ev">{evidence}</ul><h5>Policy basis</h5>{policy}</article>')


def highlight_note(review: Review) -> str:
    """The note with every cited sentence marked, coloured by the most severe criterion citing it."""
    note, spans = review.request.note_text, {}
    for r in review.checklist:
        for f in r.note_evidence:
            words = f.evidence.split()
            m = words and re.search(r"\s+".join(map(re.escape, words)), note, re.I)
            if m:
                ids, status = spans.get(m.span(), ([], "SUPPORTED"))
                if r.criterion_id not in ids:
                    ids = ids + [r.criterion_id]
                spans[m.span()] = (ids, max(status, r.status, key=SEVERITY.index))
    out, pos = [], 0
    for (start, end), (ids, status) in sorted(spans.items()):
        if start < pos:  # overlapping citation: the earlier highlight already covers it
            continue
        cited = escape(", ".join(ids))
        out += [escape(note[pos:start]), f'<mark class="hl hl--{STATUS[status][1]}" title="Cited by {cited}">',
                escape(note[start:end]), f'<sup>{cited}</sup></mark>']
        pos = end
    legend = "".join(f'<span><i class="key key--{mod}"></i>{label}</span>' for label, mod in STATUS.values())
    return (f'<div class="panel"><div class="panel-head"><h5>Clinical note</h5><div class="legend">{legend}</div>'
            f'</div><div class="note">{"".join(out)}{escape(note[pos:])}</div></div>')


def follow_ups(questions: list[str]) -> str:
    items = "".join(f'<li><span class="cid">{escape(cid)}</span>{escape(text)}</li>'
                    for cid, _, text in (q.partition(": ") for q in questions))
    return (f'<div class="panel"><div class="panel-head"><h5>Ask the provider</h5>'
            f'<span class="count">{len(questions)}</span></div><ol class="asks">{items}</ol></div>')
