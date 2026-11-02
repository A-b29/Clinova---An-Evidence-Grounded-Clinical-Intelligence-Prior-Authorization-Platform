# Clinical Claims Intelligence & Prior-Authorization Copilot

A decision-support prototype for a human prior-authorization reviewer. Given a synthetic
authorization request and clinical note, it:

1. **extracts** clinical facts into validated JSON, each tied to the exact note sentence it came from;
2. **retrieves** the relevant passages from a small set of illustrative policy documents (local RAG);
3. **checks** four demo criteria and marks each `SUPPORTED`, `NOT_FOUND`, or `CONFLICTING`;
4. **reports** an evidence-linked review with citations and follow-up questions.

> **Safety boundary.** Synthetic data and illustrative policy text only. The system never approves or
> denies, gives no medical advice, and treats `NOT_FOUND` as *"not in the supplied documents"*, never as
> *"criterion unmet"*. **Decision-support output only; human review required.**

How it works and why it was built this way: **[docs/MODEL_FLOW_AND_DECISIONS.md](docs/MODEL_FLOW_AND_DECISIONS.md)**.
Interview preparation: **[docs/RESUME_AND_INTERVIEW_PREP.md](docs/RESUME_AND_INTERVIEW_PREP.md)**.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py                                   # UI at http://localhost:8501
python -m src.pipeline PA-001                          # CLI: Markdown report
python -m src.pipeline PA-003 --json                   # CLI: full Review JSON
python -m pytest                                       # 29 tests, ~5 s, offline
python -m eval.run_eval                                # metrics -> eval/results_rules.md
```

The first run downloads the `all-MiniLM-L6-v2` embedding model (~90 MB) from Hugging Face.

### Configuration

| Env var | Default | Effect |
|---|---|---|
| `EMBEDDING_BACKEND` | `minilm` | `minilm` (semantic) or `tfidf` (lexical, no model download). MiniLM falls back to TF-IDF automatically if it can't load. |
| `ANTHROPIC_API_KEY` | unset | Enables the `llm` extractor (Claude Opus 5.5 with structured outputs) in the UI and CLI (`--extractor llm`). |

---

## Deploy

### Docker (any container host)

```bash
docker build -t pa-copilot .
docker run -p 8501:8501 pa-copilot                         # rules extractor
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=... pa-copilot  # + Claude extractor
```

The image:
- installs **CPU-only torch** (about 1 GB image instead of about 5 GB);
- **includes the embedding model** and sets `HF_HUB_OFFLINE=1`, so it never calls Hugging Face at runtime;
- **runs the test suite during the build**, so a broken commit can't produce an image;
- runs as a **non-root** user and has a **HEALTHCHECK** on Streamlit's `/_stcore/health`.

It works unchanged on Google Cloud Run, AWS App Runner / ECS, Azure Container Apps, or Hugging Face Spaces (Docker SDK).
Pass `ANTHROPIC_API_KEY` from the platform's secret manager, never bake it into the image.

### Streamlit Community Cloud

Point it at the repo with `app.py` as the entry file. Add `ANTHROPIC_API_KEY` under *Secrets* if you want
the LLM extractor. If memory is tight, set `EMBEDDING_BACKEND=tfidf`; with procedure-code routing,
retrieval scored the same on this eval set.

---

## Architecture

```text
case request + clinical note ──► ingestion ──► fact extraction (rules | Claude) ──► evidence verification
                                                                                        │
policy docs ──► heading chunks ──► MiniLM embeddings ──► vector index ──► retrieval ────┤
                                    (+ title/section headers)   (routed by procedure code)│
                                                                                        ▼
                                        rule-based criteria checklist (SUPPORTED / NOT_FOUND / CONFLICTING)
                                                                                        ▼
                                        templated, citation-linked report ──► Streamlit reviewer UI / CLI
```

| Path | Responsibility |
|---|---|
| `src/schemas.py` | Pydantic contracts (`CaseRequest`, `Fact`, `ClinicalFacts`, `CriterionResult`, `Review`) |
| `src/ingestion.py` | TXT/MD/PDF loading, heading-based policy chunking, procedure-code tags |
| `src/extraction.py` | Rule extractor (lexicon + NegEx-style negation), Claude extractor, verbatim-evidence check |
| `src/retrieval.py` | MiniLM / TF-IDF embeddings, in-memory cosine index, procedure-code routing |
| `src/assessment.py` | The four criteria, status rules, conflict detection, follow-up questions |
| `src/reporting.py` | Deterministic Markdown report |
| `src/pipeline.py` | End-to-end `review_case()` and the CLI |
| `app.py` | Streamlit UI (sample cases or upload a TXT/PDF note) |
| `eval/` | Hand-labelled expectations (`evaluation_cases.json`) and `run_eval.py` |
| `tests/` | pytest suite (schemas, extraction, retrieval, assessment) |
| `data/cases/` | 7 synthetic cases (5 dev + 2 held-out) |
| `data/policies/` | 5 illustrative policy documents (TKA, THA, knee arthroscopy, lumbar MRI, general) |

---

## Data provenance

All cases and policies were **written by hand for this project**. No real patients, providers, or payer
policies are involved. Each note begins with `SYNTHETIC CLINICAL NOTE - FICTIONAL PATIENT`, and each
policy carries an `ILLUSTRATIVE SAMPLE TEXT` banner. CPT/ICD-10 codes are real public code values,
used only as routing metadata.

| Case | Procedure | Designed to test | Split |
|---|---|---|---|
| PA-001 | Total knee arthroplasty | Complete documentation (happy path) | dev |
| PA-002 | Total knee arthroplasty | Missing imaging and conservative treatment → `NOT_FOUND` | dev |
| PA-003 | Total knee arthroplasty | Mild vs advanced imaging in two places → `CONFLICTING` | dev |
| PA-004 | Total hip arthroplasty | Complete documentation, different policy | dev |
| PA-005 | Total hip arthroplasty | Request/note diagnosis mismatch; PT both done and declined | dev |
| PA-006 | Total knee arthroplasty | Clinical shorthand ("DJD", "formal rehab", "anti-inflammatories") | held-out |
| PA-007 | Total knee arthroplasty | Explicit negations ("denies PT", "no imaging on file") | held-out |

---

## Evaluation (smoke test: 7 cases, 28 criterion decisions)

Full output: [`eval/results_rules.md`](eval/results_rules.md). Production config: rules extractor + MiniLM + routing.

| Metric | Dev (5 cases) | Held-out (2 cases) |
|---|---|---|
| Fact extraction precision / recall / F1 | 1.00 / 1.00 / 1.00 | 1.00 / 0.77 / 0.87 |
| Checklist status accuracy | 20/20 | 7/8 |
| Schema validity | 7/7 overall | |
| Evidence grounding (cited sentence verbatim in note + policy passage attached) | 28/28 overall | |
| Retrieval Hit@1 / MRR@3 | 100% / 1.00 (8 distinct queries) | |
| Failed runs | 0/7 | |
| Latency | ~40 ms per case after a one-off model load (~20 s cold) | |

**Read these numbers carefully.** The rule lexicon was written while looking at the dev notes, so dev
scores are in-sample by construction. The held-out cases show the real weakness: the rules don't know
"formal rehab" = physical therapy or "anti-inflammatories" = NSAIDs, so PA-006's conservative-treatment
criterion comes out `NOT_FOUND` instead of `SUPPORTED`. With 20 of 20 correct, the 95% Wilson lower
bound on accuracy is still only about 84%. This is a smoke test, not validation.

## Limitations

- Rule-based extraction is limited to its lexicon. The Claude extractor exists for phrasing variation but hasn't yet been evaluated against the gold set; run `python -m eval.run_eval --extractor llm` with a key.
- Negation is a NegEx-style heuristic (5-word look-back, 4-word look-ahead, pseudo-negation masking). Long-range or double negation isn't handled.
- Imaging-severity conflict is keyword-based. Two compartments of different severity in separate sentences would be flagged as `CONFLICTING`; that's a deliberate bias towards a human look.
- Laterality (left vs right), dates and recency aren't checked.
- Retrieval queries come from procedure + criterion only, so the retrieval eval has 8 distinct queries.
- No authentication, audit log, or PHI controls. **Don't upload real patient data**, especially with the LLM extractor enabled.

## Demo script (about 5 minutes)

1. `streamlit run app.py` → read the safety banner out loud.
2. **PA-001** (happy path): four green tiles. Open *Extracted facts*: every row has a verbatim evidence sentence. Open *Criteria checklist*: each criterion cites the TKA policy section it maps to.
3. **PA-002** (missing documents): imaging and conservative treatment are `NOT_FOUND`. Point out the wording *"does not establish that the criterion is unmet"* and the generated provider questions.
4. **PA-003** (conflict): C2 is `CONFLICTING` because the radiology line says *mild* and the clinic summary says *advanced, bone-on-bone*. That's exactly what a reviewer needs surfaced.
5. **PA-005**: diagnosis mismatch (request says osteoarthritis, note says avascular necrosis), and PT both "tried" and "declined".
6. *Review report* tab → download the Markdown/JSON.
7. Close with the eval table, the held-out miss on PA-006, and why that motivates the LLM extractor plus a larger labelled set.

## MVP acceptance checklist

- [x] Select or upload a synthetic case
- [x] Required fields extracted into valid structured data (Pydantic)
- [x] Relevant policy chunks retrieved and shown with document and section
- [x] Every criterion has a status with evidence, or an explicit absence of evidence
- [x] Missing documentation (`NOT_FOUND`) kept distinct from contradictory evidence (`CONFLICTING`)
- [x] Works on 7 test cases (≥3 required)
- [x] Setup, architecture, data provenance, limitations and safety boundaries documented
