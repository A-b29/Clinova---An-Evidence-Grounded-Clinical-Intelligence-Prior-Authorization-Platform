# Clinical Claims Intelligence & Prior Authorization Copilot

## One-Day MVP Project Outline

**Project type:** Healthcare NLP + RAG + GenAI\
**Target:** A demonstrable, end-to-end prototype that can be completed
in one focused day\
**Primary use case:** Help a human reviewer inspect a synthetic
prior-authorization request by extracting clinical facts, retrieving
relevant policy passages, and presenting an evidence-linked checklist.

------------------------------------------------------------------------

## 1. Problem statement

Healthcare prior-authorization requests often combine structured claim
details with unstructured clinical notes and coverage-policy documents.
Reviewing them requires locating relevant facts, checking policy
criteria, and identifying missing documentation.

Build a small decision-support prototype that:

1.  Accepts a synthetic authorization request and supporting clinical
    note.
2.  Extracts key clinical facts into a validated JSON structure.
3.  Retrieves relevant passages from a small collection of policy
    documents.
4.  Compares the extracted facts with a **small, explicitly defined set
    of criteria**.
5.  Produces an evidence-linked review summary for a human reviewer.

**Safety boundary:** This is an educational prototype using synthetic
data and sample policy text. It must not approve or deny real claims,
provide medical advice, or infer that missing documentation means a
criterion is clinically unmet. Final decisions remain with qualified
human reviewers.

------------------------------------------------------------------------

## 2. MVP scope: what we will finish today

### Must-have features

-   [ ] A small synthetic dataset: 3--5 authorization cases.
-   [ ] 3--5 short sample policy documents, clearly labelled as
    illustrative.
-   [ ] PDF or TXT ingestion (TXT is acceptable for the first working
    version).
-   [ ] Clinical fact extraction into structured JSON.
-   [ ] Policy chunking and embedding generation.
-   [ ] Vector retrieval with source-document and chunk references.
-   [ ] A transparent criteria checklist: `SUPPORTED`, `NOT_FOUND`, or
    `CONFLICTING`.
-   [ ] A generated review report with citations to retrieved passages.
-   [ ] A simple Streamlit interface or command-line demo.
-   [ ] A small evaluation set and documented limitations.

### Explicitly out of scope for today

-   Real patient data or production deployment.
-   Real insurance-policy interpretation or automated coverage
    decisions.
-   Full ICD/CPT coding, claims adjudication, fraud detection, or
    payment-integrity scoring.
-   Multi-agent orchestration, fine-tuning, complex knowledge graphs,
    and AWS deployment.
-   Claims that the prototype is clinically validated.

Keep the first version narrow. A reliable end-to-end workflow is more
valuable than several unfinished modules.

------------------------------------------------------------------------

## 3. Demonstration scenario

Use a fictional case involving a prior-authorization request for a total
knee arthroplasty.

**Synthetic case input**

-   Case ID: `PA-001`
-   Diagnosis: Osteoarthritis
-   Requested procedure: Total knee arthroplasty
-   Clinical note: Persistent knee pain, imaging described as showing
    advanced osteoarthritis, and prior physiotherapy/NSAID treatment
    with inadequate relief.
-   Supporting documents: A fictional clinical note and an illustrative
    policy document.

The policy document should contain a few clearly stated example
criteria, such as:

1.  Documentation of the relevant diagnosis.
2.  Documentation of imaging findings.
3.  Documentation of conservative treatment.
4.  Documentation of persistent symptoms and clinical rationale.

These are **demo criteria only**, not actual coverage rules. Do not
represent them as official medical or payer policy.

------------------------------------------------------------------------

## 4. End-to-end workflow

``` text
Synthetic case + clinical note + sample policy documents
                         |
                         v
                Document ingestion
                         |
              +----------+----------+
              |                     |
              v                     v
      Clinical fact extraction   Policy processing
              |                     |
              v                     v
       Pydantic validation     Chunking + embeddings
              |                     |
              |                     v
              |               Vector retrieval
              |                     |
              +----------+----------+
                         |
                         v
             Criteria evidence checklist
                         |
                         v
             Evidence-linked review report
                         |
                         v
                 Human reviewer UI
```

### Step A --- Clinical information extraction

Extract only facts explicitly present in the submitted note.

Example output:

``` json
{
  "case_id": "PA-001",
  "diagnosis": ["osteoarthritis"],
  "symptoms": ["persistent knee pain"],
  "imaging_findings": ["advanced osteoarthritis"],
  "prior_treatments": ["physiotherapy", "NSAIDs"],
  "treatment_response": "inadequate relief",
  "requested_procedure": "total knee arthroplasty",
  "uncertain_or_missing": []
}
```

Use a Pydantic model to validate the output. Preserve the source
sentence or text span for each extracted fact wherever possible. If a
field is not stated, return `null` or an empty list; do not guess.

### Step B --- Policy document RAG

1.  Load the illustrative policy documents.
2.  Split them into small, traceable chunks.
3.  Generate embeddings.
4.  Store chunks and metadata in a local vector index.
5.  Retrieve the most relevant chunks for each criterion.
6.  Display the document name, section, and exact supporting excerpt.

Start with a local vector store such as FAISS or Chroma. Use a simple
embedding model available in the environment. Avoid adding
infrastructure that is not needed for the demo.

### Step C --- Criteria evidence assessment

Use a transparent checklist rather than asking an LLM to make an
unreviewable decision.

For each demo criterion, return:

-   `SUPPORTED`: the submitted documents contain relevant evidence.
-   `NOT_FOUND`: no supporting evidence was found in the submitted
    material.
-   `CONFLICTING`: the submitted material contains evidence that appears
    inconsistent.

Each result must include: - Criterion text. - Evidence from the clinical
note, if any. - Relevant policy passage. - A short explanation. - A
confidence or uncertainty note, if available.

`NOT_FOUND` means only that the information was not found in the
supplied documents. It does not establish that the patient did not
receive the treatment or that the criterion is unmet.

### Step D --- Review report

Generate a concise report containing:

-   Case ID and requested procedure.
-   Extracted clinical facts.
-   Criteria checklist and status.
-   Clinical-note evidence.
-   Retrieved policy references.
-   Missing or conflicting documentation.
-   Questions for human follow-up.
-   A clear statement: **"Decision-support output only; human review
    required."**

------------------------------------------------------------------------

## 5. Suggested technology stack

  -----------------------------------------------------------------------
  Layer                   Suggested tool          Why
  ----------------------- ----------------------- -----------------------
  Language                Python                  Core implementation

  Data handling           Pandas                  Case and evaluation
                                                  data

  Structured extraction   LLM API or local model  Convert notes into
                                                  structured facts

  Validation              Pydantic                Enforce output schema

  NLP / embeddings        Sentence Transformers   Create document
                                                  embeddings

  Retrieval               FAISS or Chroma         Local semantic search

  Document parsing        PyMuPDF                 Optional PDF support

  Backend                 Plain Python initially; Keep the MVP simple
                          FastAPI if time permits 

  Interface               Streamlit               Fast interactive demo

  Testing                 pytest                  Check extraction,
                                                  retrieval and status
                                                  logic

  Version control         Git                     Reproducible project
                                                  history
  -----------------------------------------------------------------------

**Model choice:** Use an API or local model already available to the
team. Keep the model behind a small interface so it can be changed
without rewriting the application. Do not spend the day troubleshooting
a new provider or paid cloud service.

------------------------------------------------------------------------

## 6. Proposed repository structure

``` text
clinical-claims-copilot/
├── app.py                    # Streamlit entry point
├── data/
│   ├── cases/                # Synthetic clinical notes
│   └── policies/             # Illustrative policy documents
├── src/
│   ├── schemas.py            # Pydantic data models
│   ├── extraction.py         # Clinical fact extraction
│   ├── ingestion.py          # Document loading and chunking
│   ├── retrieval.py          # Embeddings and retrieval
│   ├── assessment.py         # Criteria evidence checklist
│   └── reporting.py          # Review report generation
├── tests/
│   ├── test_schemas.py
│   ├── test_retrieval.py
│   └── test_assessment.py
├── eval/
│   └── evaluation_cases.json # Small hand-checked test set
├── requirements.txt
└── README.md
```

If time is tight, combine modules rather than delaying the working demo
for ideal folder structure.

------------------------------------------------------------------------

## 7. One-day execution plan

  -----------------------------------------------------------------------
  Time block              Task                    Deliverable
  ----------------------- ----------------------- -----------------------
  Hour 1                  Finalize case schema,   Input data ready
                          3--5 synthetic cases    
                          and illustrative policy 
                          text                    

  Hours 2--3              Implement document      Structured JSON output
                          loading, clinical       
                          extraction and Pydantic 
                          validation              

  Hours 4--5              Implement chunking,     Working policy search
                          embeddings and          
                          retrieval with source   
                          metadata                

  Hour 6                  Implement criteria      Per-criterion
                          checklist and evidence  assessment
                          linking                 

  Hour 7                  Build Streamlit         End-to-end demo
                          interface and review    
                          report                  

  Hour 8                  Test cases, fix         Presentable MVP
                          failures and write      
                          README/limitations      
  -----------------------------------------------------------------------

**Priority rule:** If the schedule slips, preserve extraction →
retrieval → evidence checklist → report. Drop PDF support, FastAPI,
cloud deployment and visual polish before sacrificing the end-to-end
workflow.

------------------------------------------------------------------------

## 8. Evaluation plan

Use 3--5 manually checked synthetic cases. Record expected facts,
expected policy chunks, and expected criterion statuses.

  -----------------------------------------------------------------------
  Component                           What to measure today
  ----------------------------------- -----------------------------------
  Extraction                          Field-level exact match or
                                      precision/recall on key facts

  Schema reliability                  Percentage of outputs passing
                                      Pydantic validation

  Retrieval                           Whether the expected policy passage
                                      appears in top-3 results

  Evidence grounding                  Whether every assessment cites an
                                      actual source passage

  Checklist logic                     Whether known test cases produce
                                      the expected status

  Reliability                         Number of failed runs across the
                                      test set

  Latency                             Approximate processing time per
                                      case
  -----------------------------------------------------------------------

Do not claim robust clinical accuracy from 3--5 examples. Report the
sample size and treat results as a smoke test, not validation.

### Minimum acceptance criteria

The MVP is complete when:

-   [ ] A user can select or submit a synthetic case.
-   [ ] The system extracts the required fields into valid structured
    data.
-   [ ] The system retrieves relevant policy chunks and displays their
    sources.
-   [ ] Each criterion receives a status with supporting evidence or an
    explicit absence of evidence.
-   [ ] The report distinguishes missing documentation from
    contradictory evidence.
-   [ ] The demo works on at least three test cases.
-   [ ] The README explains setup, architecture, data provenance,
    limitations and safety boundaries.

------------------------------------------------------------------------

## 9. Risks and safeguards

-   **Hallucinated facts:** Require source text for extracted facts; use
    `null` when absent.
-   **Unsupported policy claims:** Use only supplied illustrative
    policies and show exact excerpts.
-   **Retrieval errors:** Display retrieved passages and allow the
    reviewer to inspect them.
-   **False certainty:** Use `SUPPORTED`, `NOT_FOUND`, and
    `CONFLICTING`; avoid automatic approval/denial.
-   **Sensitive information:** Use synthetic data only. Do not upload
    real patient records to third-party model APIs.
-   **Evaluation overclaiming:** Publish the small test-set size and
    known failure cases.

------------------------------------------------------------------------

## 10. Final deliverables by end of day

1.  A working Streamlit demo.
2.  Three to five synthetic authorization cases.
3.  A small collection of illustrative policy documents.
4.  Clinical extraction into validated JSON.
5.  Local RAG retrieval with source references.
6.  An evidence-linked criteria checklist.
7.  A generated human-review report.
8.  A README with setup instructions, architecture, evaluation results
    and limitations.
9.  A short demo script showing one complete case from input to report.

------------------------------------------------------------------------

## 11. How this maps to the Cohere Health internship JD

  JD requirement                 Evidence from this MVP
  ------------------------------ -------------------------------------
  Python and data handling       Document and case processing
  GenAI and prompt engineering   Structured clinical fact extraction
  Semantic embeddings            Policy-document embeddings
  Unstructured data              Clinical notes and policy text
  Data integration               Clinical facts + policy passages
  Model evaluation               Extraction and retrieval test set
  Rapid prototyping              Working end-to-end application
  Healthcare analytics           Prior-authorization review workflow
  Reliability and validation     Pydantic, source evidence and tests
  OOP / modular engineering      Separated application modules

This MVP will **not** demonstrate advanced SQL, AWS, production MLOps,
large-scale ETL, or real payment-integrity performance. Those should be
separate follow-up improvements rather than rushed claims.

## 12. Definition of success

At the end of today, a reviewer should be able to submit a fictional
authorization case, see what the system extracted, inspect which policy
passages were retrieved, understand why each demo criterion was marked
`SUPPORTED`, `NOT_FOUND`, or `CONFLICTING`, and review a traceable
summary.

**The goal is not to build an autonomous claims decision-maker in one
day. The goal is to demonstrate a reliable, evidence-grounded healthcare
NLP + RAG workflow that can be extended into a larger clinical
intelligence platform.**
