"""Transparent criteria checklist: every status comes from a readable rule, not an LLM verdict.

SUPPORTED   - every required fact type has at least one affirmed mention, and no conflicts.
NOT_FOUND   - some required fact type has no affirmed mention. This says nothing about
              whether the care happened; documentation may simply be missing.
CONFLICTING - the submitted material disagrees with itself or with the request.
"""
import re
from typing import NamedTuple

from .extraction import DIAGNOSES, match_terms
from .retrieval import PolicyIndex
from .schemas import CaseRequest, ClinicalFacts, CriterionResult, Fact

SEVERE = re.compile(r"advanced|severe|bone-on-bone|end-stage|marked|collapse|grade (?:3|4|III|IV)\b", re.I)
MILD = re.compile(r"\bmild\b|minimal|\bearly\b|no significant|unremarkable|\bnormal\b|\bno (?:\w+ )?evidence of", re.I)


class Criterion(NamedTuple):
    id: str
    text: str
    fields: tuple[str, ...]  # fact types that must each have an affirmed mention
    query: str               # retrieval query, prefixed with the requested procedure


CRITERIA = [
    Criterion("C1", "Documentation of the relevant diagnosis", ("diagnosis",),
              "diagnosis stated in the clinical note supporting the request"),
    Criterion("C2", "Documentation of imaging findings", ("imaging_findings",),
              "imaging findings radiographs X-ray MRI of the affected joint"),
    Criterion("C3", "Documentation of conservative treatment and response", ("prior_treatments", "treatment_response"),
              "conservative nonsurgical treatment physical therapy NSAIDs injections and response"),
    Criterion("C4", "Documentation of persistent symptoms and clinical rationale", ("symptoms", "symptom_duration"),
              "persistent symptoms pain duration functional limitation clinical rationale"),
]

FIELD_LABELS = {"diagnosis": "diagnosis", "imaging_findings": "imaging findings",
                "prior_treatments": "conservative treatments", "treatment_response": "response to treatment",
                "symptoms": "symptoms", "symptom_duration": "symptom duration/persistence"}


def policy_query(c: Criterion, request: CaseRequest) -> str:
    return f"{request.requested_procedure}: {c.query}"


def _conflicts(c: Criterion, facts: ClinicalFacts, request: CaseRequest) -> list[str]:
    issues = []
    for field in c.fields:
        items = getattr(facts, field)
        both = {f.value for f in items if not f.negated} & {f.value for f in items if f.negated}
        issues += [f"'{v}' is documented in one place and negated in another" for v in sorted(both)]

    if c.id == "C1":
        requested = match_terms(request.diagnosis, DIAGNOSES)
        affirmed = {f.value for f in facts.diagnosis if not f.negated}
        if requested and affirmed and not requested & affirmed:
            issues.append(f"request lists '{request.diagnosis}' but the note documents {', '.join(sorted(affirmed))}")
        if requested and not affirmed and requested & {f.value for f in facts.diagnosis if f.negated}:
            issues.append(f"request diagnosis '{request.diagnosis}' is negated in the note")

    if c.id == "C2":
        affirmed = [f for f in facts.imaging_findings if not f.negated]
        if affirmed and any(f.negated for f in facts.imaging_findings):
            issues.append("imaging findings are described, but the note also states imaging is not available")
        # Compare across separate statements only: one report saying "early collapse" isn't a conflict.
        severe = [f for f in affirmed if SEVERE.search(f.value)]
        mild = [f for f in affirmed if MILD.search(f.value) and f not in severe]
        if severe and mild:
            issues.append(f"imaging severity differs between statements: '{mild[0].value}' vs '{severe[0].value}'")

    if c.id == "C3":
        responses = {f.value for f in facts.treatment_response}
        if "adequate relief" in responses:
            issues.append("note describes relief from conservative treatment"
                          + (" and also inadequate relief" if "inadequate relief" in responses else
                             ", which appears inconsistent with the request"))
    return issues


def assess(facts: ClinicalFacts, request: CaseRequest, index: PolicyIndex, k: int = 3) -> list[CriterionResult]:
    results = []
    for c in CRITERIA:
        evidence: list[Fact] = [f for field in c.fields for f in getattr(facts, field)]
        missing = [field for field in c.fields if not any(not f.negated for f in getattr(facts, field))]
        issues = _conflicts(c, facts, request)

        if issues:
            joined = "; ".join(issues)
            status, explanation = "CONFLICTING", joined[0].upper() + joined[1:] + "."
        elif not missing:
            values = sorted({f.value for f in evidence})
            status, explanation = "SUPPORTED", f"Note documents: {', '.join(values)}."
        else:
            status = "NOT_FOUND"
            explanation = f"No affirmed mention of {' or '.join(FIELD_LABELS[m] for m in missing)} in the submitted note."
            negated = sorted({f.value for f in evidence if f.negated})
            if negated:
                explanation += f" The note states these were not done or are not available: {', '.join(negated)}."
            explanation += " This does not establish that the criterion is unmet."

        results.append(CriterionResult(
            criterion_id=c.id, criterion=c.text, status=status, note_evidence=evidence,
            policy_passages=index.search(policy_query(c, request), k=k, procedure_code=request.procedure_code),
            explanation=explanation,
            uncertainty="Status is rule-based over extracted facts; phrasing the extractor does not recognise "
                        "will appear as NOT_FOUND. Check the cited sentences and policy passages.",
        ))
    return results


def follow_up_questions(checklist: list[CriterionResult], request: CaseRequest) -> list[str]:
    questions = []
    for r in checklist:
        if r.status == "NOT_FOUND":
            questions.append(f"{r.criterion_id}: Can the provider supply documentation for "
                             f"'{r.criterion.lower()}' for the requested {request.requested_procedure.lower()}?")
        elif r.status == "CONFLICTING":
            questions.append(f"{r.criterion_id}: Please clarify the inconsistency: {r.explanation}")
    return questions
