from types import SimpleNamespace

import pytest

from src.extraction import LLM_MODEL, extract
from src.schemas import CaseRequest, ClinicalFacts, Fact


def request(note: str) -> CaseRequest:
    return CaseRequest(case_id="T-1", requested_procedure="Total knee arthroplasty",
                       diagnosis="Osteoarthritis of the knee", note_text=note)


@pytest.mark.parametrize("note, negated", [
    ("Pt denies prior physical therapy.", True),
    ("Patient declined physical therapy.", True),
    ("Patient has not attended physical therapy.", True),
    ("Completed physical therapy with no improvement.", False),  # pseudo-negation: describes response
    ("Physical therapy did not help.", False),
    ("Completed 8 weeks of PT.", False),
])
def test_treatment_negation(note, negated):
    [fact] = extract(request(note)).prior_treatments
    assert fact.value == "physical therapy" and fact.negated is negated


def test_pt_abbreviation_is_case_sensitive():
    assert extract(request("Pt reports knee pain.")).prior_treatments == []


def test_imaging_requires_a_result():
    assert extract(request("Plan: obtain X-ray of the knee.")).imaging_findings == []
    [fact] = extract(request("Imaging has not yet been obtained.")).imaging_findings
    assert fact.negated
    [fact] = extract(request("XR L knee: bone-on-bone medial compartment.")).imaging_findings
    assert fact.value == "bone-on-bone medial compartment" and not fact.negated
    [fact] = extract(request("No radiographic evidence of osteoarthritis.")).imaging_findings
    assert not fact.negated  # a normal result is still an imaging finding


def test_every_rule_fact_cites_a_note_sentence():
    note = "Knee pain for 2 years. Assessment: OA of the knee. Took naproxen with inadequate relief."
    facts = extract(request(note))
    cited = [f for field in ("diagnosis", "symptoms", "prior_treatments", "treatment_response")
             for f in getattr(facts, field)]
    assert cited and all(f.evidence in note for f in cited)


class FakeClient:
    """Stands in for anthropic.Anthropic(); returns a canned structured-output response."""
    def __init__(self, parsed, stop_reason="end_turn"):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))
        self._response = SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_llm_extractor_drops_hallucinated_evidence():
    note = "Assessment: osteoarthritis of the right knee."
    parsed = ClinicalFacts(case_id="WRONG", diagnosis=[
        Fact(value="osteoarthritis", evidence="Assessment: osteoarthritis of the right knee."),
        Fact(value="rheumatoid arthritis", evidence="History of rheumatoid arthritis."),  # not in note
    ])
    client = FakeClient(parsed)
    facts = extract(request(note), "llm", client)
    assert [f.value for f in facts.diagnosis] == ["osteoarthritis"]
    assert facts.case_id == "T-1"  # identity comes from the request, not the model
    assert any("dropped 1 fact" in m for m in facts.uncertain_or_missing)
    assert client.calls[0]["model"] == LLM_MODEL and client.calls[0]["output_format"] is ClinicalFacts


def test_llm_refusal_raises():
    with pytest.raises(RuntimeError):
        extract(request("Knee pain."), "llm", FakeClient(None, stop_reason="refusal"))
