import pytest
from pydantic import ValidationError

from src.schemas import CaseRequest, ClinicalFacts, CriterionResult, Fact


def test_case_request_rejects_empty_note():
    with pytest.raises(ValidationError):
        CaseRequest(case_id="X", requested_procedure="TKA", diagnosis="OA", note_text="")


def test_clinical_facts_defaults_and_round_trip():
    facts = ClinicalFacts(case_id="X", diagnosis=[Fact(value="osteoarthritis", evidence="Dx: OA.")])
    assert facts.imaging_findings == [] and facts.uncertain_or_missing == []
    assert ClinicalFacts.model_validate_json(facts.model_dump_json()) == facts


def test_status_cannot_be_an_approval_decision():
    with pytest.raises(ValidationError):
        CriterionResult(criterion_id="C1", criterion="x", status="APPROVED", note_evidence=[],
                        policy_passages=[], explanation="", uncertainty="")
