"""Pydantic data contracts shared by every pipeline stage."""
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["SUPPORTED", "NOT_FOUND", "CONFLICTING"]


class CaseRequest(BaseModel):
    """Structured fields of a prior-authorization request plus the clinical note text."""
    case_id: str
    requested_procedure: str
    diagnosis: str
    procedure_code: str | None = None
    diagnosis_code: str | None = None
    note_text: str = Field(min_length=1)


class Fact(BaseModel):
    """One clinical fact, always tied to the exact note sentence it came from."""
    value: str = Field(description="Normalized term, e.g. 'physical therapy'")
    evidence: str = Field(description="Verbatim sentence copied from the clinical note")
    negated: bool = Field(default=False, description="True if the note states this is absent / not done")


class ClinicalFacts(BaseModel):
    case_id: str
    diagnosis: list[Fact] = []
    symptoms: list[Fact] = []
    symptom_duration: list[Fact] = []
    imaging_findings: list[Fact] = []
    prior_treatments: list[Fact] = []
    treatment_response: list[Fact] = []
    requested_procedure: str | None = None
    uncertain_or_missing: list[str] = []


FACT_FIELDS = ["diagnosis", "symptoms", "symptom_duration", "imaging_findings",
               "prior_treatments", "treatment_response"]


class PolicyChunk(BaseModel):
    chunk_id: str
    document: str
    title: str
    section: str
    text: str
    procedure_codes: list[str] = []  # empty = applies to every request


class RetrievedChunk(PolicyChunk):
    score: float


class CriterionResult(BaseModel):
    criterion_id: str
    criterion: str
    status: Status
    note_evidence: list[Fact]
    policy_passages: list[RetrievedChunk]
    explanation: str
    uncertainty: str


class Review(BaseModel):
    request: CaseRequest
    facts: ClinicalFacts
    checklist: list[CriterionResult]
    follow_up_questions: list[str]
    extractor: str
    retriever: str
    latency_ms: float
