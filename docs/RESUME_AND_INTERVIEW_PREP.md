# Resume Entry & Interview Prep: Prior-Authorization Copilot

Use this to (1) put the project on your resume, (2) explain it in 30 seconds, 2 minutes, or 20 minutes,
and (3) answer the follow-up questions interviewers ask about healthcare NLP, RAG, and LLM evaluation.
All numbers come from `python -m eval.run_eval`. Re-run it before an interview and quote only what it prints.

---

## 1. Resume entry

### Full version (Projects section)

**Clinical Claims Intelligence & Prior-Authorization Copilot** | *Python, Pydantic, Sentence-Transformers, RAG, Claude API, Streamlit, Docker, pytest*

- Built an end-to-end healthcare NLP + RAG decision-support tool that extracts clinical facts from prior-authorization notes into Pydantic-validated JSON, retrieves policy passages, and produces an evidence-linked `SUPPORTED / NOT_FOUND / CONFLICTING` checklist for human reviewers.
- Designed hallucination safeguards: every extracted fact must quote a sentence found verbatim in the note (unverifiable LLM facts are dropped and logged), criteria are decided by auditable rules rather than an LLM judge, and the schema makes approve/deny outputs impossible.
- Found through a retrieval ablation that semantic search ranked a look-alike knee-arthroscopy policy above the knee-replacement policy; added contextual chunk headers and procedure-code routing, raising Hit@1 from 82% to 100% (MRR 0.91 → 1.00).
- Built an evaluation harness with dev and held-out splits (fact-level P/R/F1, status accuracy, grounding, latency), reported the held-out recall gap (0.77) instead of the in-sample 100%, and shipped a tested Docker image (29 tests run during the build, offline model, non-root, health check).

### Two-line version (when space is tight)

**Prior-Authorization Review Copilot (Healthcare NLP + RAG)**: Extracts evidence-linked clinical facts (Pydantic, Claude structured outputs), retrieves policy passages (MiniLM embeddings, procedure-code routing, Hit@1 82% → 100%), and flags missing or conflicting documentation for human review; evaluated on dev/held-out splits and deployed with Docker.

### Keywords for ATS / skills line
`NLP` `RAG` `semantic search` `sentence embeddings` `information extraction` `negation detection (NegEx)` `LLM structured outputs` `prompt engineering` `hallucination mitigation` `Pydantic` `evaluation (precision/recall/F1, MRR, Hit@k)` `ablation study` `Streamlit` `Docker` `pytest` `healthcare / prior authorization / utilization management`

> **Choose bullets for the role.** For a data-science role, lead with the evaluation and ablation bullets. For an ML-engineering role, lead with Docker, testing and schemas. For a GenAI role, lead with structured outputs and hallucination safeguards.

---

## 2. Pitches

### 30 seconds
"Prior authorization means a reviewer reads a clinical note and checks it against a payer's policy, which is slow and error-prone. I built a decision-support copilot that pulls the relevant clinical facts out of the note, each one tied to the exact sentence it came from. It retrieves the matching policy sections and tells the reviewer, criterion by criterion, whether the evidence is supported, missing, or conflicting. It never approves or denies. The interesting part was evaluation: an ablation showed semantic search was picking a look-alike policy, and a held-out set showed where my rule-based extractor breaks."

### 2 minutes (adds the how)
1. **Problem:** reviewers combine structured request fields, free-text notes, and policy documents. The expensive part is finding evidence and spotting gaps.
2. **Extraction:** a deterministic rule extractor by default (lexicons plus NegEx-style negation), with an optional Claude extractor behind the same interface using schema-constrained structured outputs. Either way, every fact must quote a sentence that appears verbatim in the note, or it is dropped.
3. **Retrieval:** policies are chunked by section heading, so each chunk is citable, then embedded with MiniLM together with the document title and section header. Search is routed by procedure code, the way real utilization-management policies are keyed.
4. **Assessment:** four explicit criteria with readable rules. `NOT_FOUND` means "not in the documents", never "criterion unmet". `CONFLICTING` means the documents disagree, for example mild versus bone-on-bone imaging.
5. **Evaluation:** 7 synthetic cases with dev and held-out splits. 100% on dev is in-sample. Held-out recall is 0.77 because the rules don't know "formal rehab" means physical therapy. That's the argument for the LLM extractor and more labelled data.
6. **Delivery:** Streamlit UI, CLI, 29 tests, and a Docker image that runs offline.

### 20-minute deep dive
Follow `docs/MODEL_FLOW_AND_DECISIONS.md` §2: trace case **PA-003** live in the UI. Then go through the decision log (D1, D2, D5, D10) and the ablation table.

---

## 3. Numbers to know cold

| What | Number | Caveat to say out loud |
|---|---|---|
| Cases / criteria / chunks | 7 cases (5 dev + 2 held-out), 4 criteria, 22 policy chunks from 5 documents | Smoke test, not validation |
| Dev fact F1 | 1.00 (42/42) | In-sample: the rules were written while reading these notes |
| Held-out fact recall | 0.77 (10/13) | The real signal: synonym gaps |
| Checklist accuracy | 20/20 dev, 7/8 held-out | 20/20 still has a 95% Wilson lower bound of about 84% |
| Retrieval Hit@1 | 82% → 100% with routing | Only 8 distinct queries; Hit@3 saturated at 100% everywhere |
| TF-IDF contextual headers | Hit@1 14% → 82% | Headers mattered for lexical, not for MiniLM |
| Latency | about 40 ms per case after the model loads (about 20 s cold) | CPU, rules extractor |
| Grounding | 28/28 criteria cite verbatim evidence plus a policy passage | By construction for rules; meaningful for the LLM |

---

## 4. STAR stories

**S1. The look-alike policy (debugging with data).**
*Situation:* Retrieval scored Hit@3 = 100%, which looked done. *Task:* make sure reviewers see the *right* policy first. *Action:* I added Hit@1 and MRR, and printed every rank-1 miss. MiniLM ranked the **knee-arthroscopy** "Imaging" section above the **knee-replacement** imaging criterion for every knee case: same joint, same vocabulary, wrong procedure. I ran an ablation of embedding backend × contextual headers × procedure-code routing. *Result:* routing took Hit@1 from 82% to 100%. Lesson: a saturated metric hides failures, and domain structure (policies keyed by CPT code) beat a fancier model.

**S2. Reporting the number that looks worse (integrity in evaluation).**
*Situation:* Dev scores were perfect. *Task:* get an honest estimate. *Action:* I wrote two held-out notes in clinical shorthand and froze the lexicon before running them. *Result:* recall fell to 0.77, and one criterion flipped to `NOT_FOUND`. I reported both splits, explained that the failure is in the *safe* direction (it produces a follow-up question, not a false "supported"), and used it to justify the LLM extractor.

**S3. Designing for safety, not just accuracy.**
*Situation:* A system that says "unmet" when documentation is merely missing could harm patients. *Action:* I limited the output to three evidence states, made `APPROVED`/`DENIED` unrepresentable in the Pydantic schema (a test enforces it), kept `NOT_FOUND` explanations explicit that the criterion isn't established as unmet, and kept the LLM out of the decision path. *Result:* every status is explainable from cited sentences and a readable rule.

**S4. A subtle NLP bug caught by thinking about failure modes.**
*Action:* While writing negation tests, I noticed that "Pt denies…" (patient) would match "PT" (physical therapy) under case-insensitive regex, and that "PT with no improvement" would look negated. *Fix:* case-sensitive abbreviations, plus NegEx-style pseudo-negation masking. Each fix is pinned by a parametrized test.

---

## 5. Technical questions with model answers

**Design and approach**

1. **Why not just give the note and the policy to an LLM and ask whether it meets criteria?**
   It's unauditable and non-deterministic, it can hallucinate evidence, and coverage-adjacent decisions need specific, traceable reasons. I use the LLM only where it's strongest, turning messy text into structured facts, and then verify its output against the source. The decision logic stays in rules a reviewer can read.

2. **How do you prevent hallucinations?**
   Four layers: (1) schema-constrained structured output, so the shape is guaranteed; (2) every fact's evidence must be a verbatim substring of the note, or it's dropped and logged; (3) identity fields (case ID, procedure) are taken from the request, never from the model; (4) the report is a template, so there's no generated prose to hallucinate.

3. **Why is rule-based extraction the default?**
   It's offline, free and deterministic, and it keeps PHI on-premises. It made a reproducible baseline for the evaluation harness. The weakness, synonyms, is measured (held-out recall 0.77), and the LLM extractor plugs into the same interface.

4. **Explain your negation detection.**
   NegEx-style: a trigger such as *no, denies, declined, without* in the 5 words before a term, or *not/never* in the 4 words after it ("imaging has not been obtained"). Pseudo-negations like "no improvement" or "did not help" are masked first, because they describe the treatment response, not absence. It fails on long-range scope ("PT was recommended, which the patient did not pursue"); the fix is dependency-based scope (medspaCy ConText) or the LLM.

5. **`NOT_FOUND` vs `CONFLICTING`: why does the distinction matter?**
   `NOT_FOUND` is a documentation gap: ask the provider. `CONFLICTING` is an inconsistency: a human must resolve which statement is true. Merging them, or turning `NOT_FOUND` into "unmet", would penalize patients for paperwork gaps.

6. **What's the precision/recall trade-off here?**
   A false `SUPPORTED` is the costly error, because it hides a gap. A false `NOT_FOUND` only triggers a question. So `SUPPORTED` requires affirmed evidence for every required fact type, while conflict detection deliberately leans towards recall (it flags for a human).

**Retrieval / RAG**

7. **Why chunk by heading instead of fixed token windows?** A policy section is the unit a reviewer cites. Heading chunks keep the criterion intact and give a clean `document § section` citation. Long sections get a paragraph sub-split at 120 words.

8. **Why MiniLM?** It's small (90 MB, 384-d), runs fast on CPU, is local (no PHI egress) and good at general sentence similarity. I'd only switch to a larger or clinical embedding model (e5/bge/gte families) if a measured retrieval eval on a bigger corpus showed a gain.

9. **Cosine similarity, and why normalize?** Cosine is the dot product of L2-normalized vectors. Normalizing once at indexing means search is a single matrix-vector product.

10. **Why no FAISS or Chroma?** 22 chunks: brute force is sub-millisecond and adds no dependencies. Past roughly 100k chunks I'd use an ANN index (HNSW, or IVF-PQ for memory), or pgvector if the policies already live in Postgres with metadata filters.

11. **What are contextual chunk headers?** Prepending "document title | section" to the text before embedding. A chunk saying "imaging of the affected knee" doesn't say *which procedure's policy* it is. Measured effect: TF-IDF Hit@1 went from 14% to 82%.

12. **Hit@k and MRR, and why did Hit@3 saturate?** Hit@k: is the right passage in the top k? MRR: the mean of 1/rank. With only two plausible policies per query, the right one is almost always in the top 3, so Hit@3 can't separate configurations. Hit@1 and MRR can.

13. **Would hybrid search help?** BM25 plus dense with reciprocal-rank fusion usually helps with exact clinical terms and codes. Here, with routing, both backends already tie at 100%, so I'd only add it once a larger corpus shows a measured gap.

**Evaluation and statistics**

14. **Your dev accuracy is 100%. Is it perfect?** No. It's in-sample. The held-out split shows recall 0.77, and with n = 20 even a perfect score has a 95% Wilson lower bound of about 84%. I'd call it a passing smoke test.

15. **How would you build a real evaluation set?** Write annotation guidelines with clinical reviewers; double-annotate and measure inter-annotator agreement (Cohen's κ); adjudicate disagreements; stratify by procedure, provider and note style; hold out by time or provider to catch drift. Size the set from the confidence-interval width you need per criterion.

16. **How would you evaluate the LLM extractor?** Use the same harness (`--extractor llm`): per-field P/R/F1, the rate of facts dropped by verification (a hallucination proxy), schema validity, latency and cost per case, repeated runs for variance, and an effort-level sweep. Compare against rules on the *same* gold set.

**Production, safety, compliance**

17. **How do you handle PHI / HIPAA?** The prototype uses synthetic data only. In production: send PHI only to vendors under a BAA, apply minimum-necessary data, encrypt in transit and at rest, use role-based access, keep an audit log of every review, and never train on PHI without authorization.

18. **Prompt injection through a clinical note?** The LLM only extracts facts. Its output still has to quote real sentences, and statuses come from rules, so injected text can't produce a "supported" verdict by instruction. I'd still add red-team tests.

19. **How would you monitor it in production?** Track `NOT_FOUND` and `CONFLICTING` rates per criterion and procedure, the reviewer override rate (the key quality signal), the verification-drop rate for the LLM, and latency and cost. Run in shadow mode before any workflow change, and feed overrides back into the labelled set.

20. **How does it scale?** Embed policies once and cache them; use an ANN index; route by code; run extraction asynchronously or with the Batch API for backlogs. Extraction is per-note and independent, so it scales horizontally.

21. **Fairness concerns?** Documentation quality varies by clinic resources. A high `NOT_FOUND` rate could fall disproportionately on under-resourced providers, so I'd monitor rates by provider segment and keep humans deciding.

22. **Why Pydantic?** It's the contract between every stage: it validates LLM output, documents the interface, and gives JSON export for the UI and audit.

23. **Structured outputs vs "please return JSON"?** Structured outputs constrain decoding to the JSON schema, so the response parses into the model or fails clearly. Prompted JSON can drift (missing fields, trailing prose).

24. **How would you add confidence?** Today it's an explanation plus an uncertainty note. A probability is only meaningful if it's calibrated. With LLM extraction and enough labels I'd calibrate per-field confidence (reliability diagrams) and abstain, routing to a human, below a threshold.

25. **What would you do with two more weeks?** Run and report the LLM extractor on the gold set; add laterality and date/recency checks; get 50+ clinician-labelled cases; add a FastAPI endpoint and audit log; widen the policy corpus and re-run the ablation.

---

## 6. Healthcare domain primer (expect at least one of these)

- **Prior authorization (PA):** the payer requires approval *before* a service, to confirm medical necessity under its coverage policy. It's part of **utilization management (UM)**.
- **Parties:** the *provider* submits; the *payer* (health plan) reviews. Nurses and physician reviewers apply clinical criteria. Only a clinician can issue an adverse determination.
- **Codes:** **CPT/HCPCS** identify procedures (27447 = total knee arthroplasty, 27130 = total hip arthroplasty). **ICD-10-CM** identifies diagnoses (M17.11 = unilateral primary osteoarthritis, right knee).
- **Criteria sets:** commercial criteria such as **InterQual** and **MCG**, plus each payer's own medical policies. This project's criteria are illustrative only.
- **Regulation:** the CMS Interoperability & Prior Authorization Final Rule (**CMS-0057-F**, 2024) requires impacted payers to meet decision timeframes (72 hours expedited, 7 days standard), give specific denial reasons, and build FHIR prior-authorization APIs (HL7 **Da Vinci** CRD / DTR / PAS guides). *Check the current effective dates before an interview.*
- **Why AI here:** most of the reviewer's time goes on finding evidence in long documents. Extraction plus retrieval with citations shortens that, while the clinical judgment stays human.

---

## 7. Limitations: how to say them confidently

| Limitation | How to phrase it |
|---|---|
| Tiny synthetic dataset | "It's a smoke test. I report the sample size and confidence intervals, and I'd scale with clinician-labelled cases." |
| Rule extractor misses synonyms | "Measured: held-out recall 0.77. That's why the extractor sits behind an interface with an LLM option." |
| LLM path not yet benchmarked | "The harness supports it (`--extractor llm`). I didn't have an API key during the build, so I haven't claimed a number." |
| No laterality or date checks | "Known gap, listed in the failure-mode table, with a specific fix." |
| Not production | "The Docker image is deployable for a demo. Production needs BAA-covered vendors, auth, an audit log and monitoring; I can walk through that list." |

---

## 8. Own the code

Interviewers often ask you to change something live. Before an interview, make sure you can explain every file and do these in under 15 minutes each:

1. Add `"formal rehab"` and `"anti-inflammator"` to `TREATMENTS` in `src/extraction.py`, re-run `python -m eval.run_eval`, and explain why held-out recall changes **and** why that's now contaminated (you tuned on the held-out set).
2. Add a laterality conflict to C1 in `src/assessment.py` (request "right" vs note "left"), with a test.
3. Wrap `review_case()` in a FastAPI `POST /review` endpoint.
4. Run `python -m eval.run_eval --extractor llm` with an API key and compare against rules.

If you used AI assistance to build the project, say so plainly if asked, and show you own it by explaining the decisions and extending the code live. That is what interviewers are actually checking.

---

## 9. Questions to ask the interviewer

1. "How do reviewers interact with AI suggestions today: do they see evidence citations, and how do you measure override rates?"
2. "How are clinical criteria versioned, and how quickly do policy changes reach production models?"
3. "What does your labelled data look like? Who annotates it, and how do you measure agreement?"
4. "Where do you draw the line between automation and human clinical judgment, especially for adverse determinations?"
5. "What would success look like for this role after three months?"

---

## 10. Pre-interview checklist

- [ ] `python -m pytest` → 29 passed
- [ ] `python -m eval.run_eval` → numbers match §3
- [ ] Demo PA-001 → PA-002 → PA-003 → PA-005 in the UI (README demo script)
- [ ] Push to GitHub with the README rendered; optionally deploy the Docker image and link it
- [ ] Be able to draw the flow diagram from `MODEL_FLOW_AND_DECISIONS.md` §1 from memory
- [ ] Prepare one sentence for each of D1, D2, D5, D10
