import json
from pathlib import Path

import pytest

from src.ingestion import load_cases, load_policies
from src.pipeline import review_case
from src.reporting import DISCLAIMER, to_markdown
from src.retrieval import PolicyIndex
from src.schemas import CaseRequest

INDEX = PolicyIndex(load_policies(), backend="tfidf")
CASES = {req.case_id: (req, split) for req, split in load_cases()}
GOLD = json.loads((Path(__file__).parent.parent / "eval" / "evaluation_cases.json").read_text())["cases"]


def statuses(note: str, diagnosis: str = "Osteoarthritis of the knee") -> dict[str, str]:
    req = CaseRequest(case_id="T", requested_procedure="Total knee arthroplasty", procedure_code="27447",
                      diagnosis=diagnosis, note_text=note)
    return {r.criterion_id: r.status for r in review_case(req, INDEX).checklist}


@pytest.mark.parametrize("gold", [g for g in GOLD if CASES[g["case_id"]][1] == "dev"], ids=lambda g: g["case_id"])
def test_dev_cases_match_gold_statuses(gold):
    review = review_case(CASES[gold["case_id"]][0], INDEX)
    assert {r.criterion_id: r.status for r in review.checklist} == gold["expected_status"]


def test_adequate_relief_is_flagged_not_supported():
    assert statuses("Completed physical therapy with good relief.")["C3"] == "CONFLICTING"


def test_negated_request_diagnosis_is_conflicting():
    assert statuses("No radiographic evidence of osteoarthritis.")["C1"] == "CONFLICTING"


def test_not_found_never_claims_criterion_unmet():
    review = review_case(CASES["PA-002"][0], INDEX)
    not_found = [r for r in review.checklist if r.status == "NOT_FOUND"]
    assert not_found and all("does not establish that the criterion is unmet" in r.explanation for r in not_found)
    assert len(review.follow_up_questions) == len(not_found)


def test_report_has_disclaimer_and_citations():
    review = review_case(CASES["PA-003"][0], INDEX)
    md = to_markdown(review)
    assert DISCLAIMER in md and "CONFLICTING" in md and "policy_total_knee_arthroplasty.md §" in md
