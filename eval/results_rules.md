# Evaluation results (extractor: `rules`)

Synthetic smoke test: 7 cases (5 dev, 2 held-out), 4 criteria each, 22 policy chunks from 5 documents. Not clinical validation.

## Retrieval ablation (is the expected policy section retrieved?)

| Backend | Contextual headers | Procedure-code routing | Hit@1 | Hit@3 | MRR@3 | Index build (s) |
|---|---|---|---|---|---|---|
| minilm | no | no | 82% | 100% | 0.91 | 20.7 |
| minilm | yes | no | 82% | 100% | 0.91 | 0.2 |
| minilm | yes | yes | 100% | 100% | 1.00 | 0.2 |
| tfidf | no | no | 14% | 100% | 0.48 | 0.0 |
| tfidf | yes | no | 82% | 100% | 0.91 | 0.0 |
| tfidf | yes | yes | 100% | 100% | 1.00 | 0.0 |

28 lookups but only 8 distinct queries: the query is built from procedure + criterion, not the note. The first MiniLM build includes model loading.

## Extraction (field-level facts, micro-averaged)

| Split | Precision | Recall | F1 | TP / FP / FN |
|---|---|---|---|---|
| dev | 1.00 | 1.00 | 1.00 | 42 / 0 / 0 |
| heldout | 1.00 | 0.77 | 0.87 | 10 / 0 / 3 |

## Checklist, grounding, reliability

| Metric | Value |
|---|---|
| Checklist status accuracy (dev) | 20/20 (100%) |
| Checklist status accuracy (heldout) | 7/8 (88%) |
| Schema validity (Pydantic) | 7/7 |
| Evidence grounding (cited sentence verbatim in note + policy passage attached) | 28/28 |
| Failed runs | 0/7 |
| Mean latency per case, excl. index build | 36 ms |

## Error analysis

- PA-006 (heldout) missed fact `prior_treatments: NSAIDs`
- PA-006 (heldout) missed fact `prior_treatments: physical therapy`
- PA-006 (heldout) missed fact `symptoms: functional limitation`
- PA-006 (heldout) C3: expected SUPPORTED, got NOT_FOUND. No affirmed mention of conservative treatments in the submitted note. This does not establish that the criterion is unmet.
