"""Smoke-test evaluation over the synthetic cases. Prints and writes eval/results_<extractor>.md.

    python -m eval.run_eval                  # rule extractor (offline)
    python -m eval.run_eval --extractor llm  # Claude extractor (needs ANTHROPIC_API_KEY)

7 cases is a smoke test, not validation. Numbers are reported per split so the
dev/held-out gap stays visible.
"""
import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from src.assessment import CRITERIA, policy_query
from src.ingestion import load_cases, load_policies
from src.pipeline import review_case
from src.retrieval import BACKENDS, PolicyIndex
from src.schemas import FACT_FIELDS, ClinicalFacts

HERE = Path(__file__).parent
FREE_TEXT_FIELDS = {"imaging_findings", "symptom_duration"}


def fact_keys(facts: ClinicalFacts) -> set[tuple[str, str]]:
    return {(field, ("NOT " if f.negated else "") + ("<documented>" if field in FREE_TEXT_FIELDS else f.value))
            for field in FACT_FIELDS for f in getattr(facts, field)}


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def retrieval_scores(index: PolicyIndex, gold: dict, cases: dict, routed: bool, k: int = 3):
    """Hit@1, Hit@k, MRR@k for the expected (document, section), plus the number of distinct queries."""
    ranks, queries = [], set()
    for g in gold["cases"]:
        request = cases[g["case_id"]][0]
        for c in CRITERIA:
            want = (g["expected_policy_document"], gold["criterion_sections"][c.id])
            query = policy_query(c, request)
            queries.add((query, request.procedure_code))
            hits = index.search(query, k=k, procedure_code=request.procedure_code if routed else None)
            ranked = [(p.document, p.section) for p in hits]
            ranks.append(ranked.index(want) + 1 if want in ranked else None)
    return (statistics.mean(r == 1 for r in ranks), statistics.mean(r is not None for r in ranks),
            statistics.mean(1 / r if r else 0.0 for r in ranks), len(queries))


def norm(s: str) -> str:
    return " ".join(s.split()).lower()


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    args = parser.parse_args(argv)

    gold = json.loads((HERE / "evaluation_cases.json").read_text(encoding="utf-8"))
    cases = {req.case_id: (req, split) for req, split in load_cases()}
    chunks = load_policies()
    out = [f"# Evaluation results (extractor: `{args.extractor}`)", "",
           f"Synthetic smoke test: {len(gold['cases'])} cases "
           f"({sum(s == 'dev' for _, s in cases.values())} dev, {sum(s == 'heldout' for _, s in cases.values())} held-out), "
           f"{len(CRITERIA)} criteria each, {len(chunks)} policy chunks from 5 documents. Not clinical validation.", ""]

    # 1. Retrieval ablation: embedding backend x contextual chunk headers x procedure-code routing.
    out += ["## Retrieval ablation (is the expected policy section retrieved?)", "",
            "| Backend | Contextual headers | Procedure-code routing | Hit@1 | Hit@3 | MRR@3 | Index build (s) |",
            "|---|---|---|---|---|---|---|"]
    for backend in BACKENDS:
        for headers, routed in ((False, False), (True, False), (True, True)):
            t = time.perf_counter()
            idx = PolicyIndex(chunks, backend=backend, contextual_headers=headers)
            build = time.perf_counter() - t
            hit1, hit3, mrr, n_queries = retrieval_scores(idx, gold, cases, routed)
            out.append(f"| {idx.backend} | {'yes' if headers else 'no'} | {'yes' if routed else 'no'} "
                       f"| {hit1:.0%} | {hit3:.0%} | {mrr:.2f} | {build:.1f} |")
    out += ["", f"{len(gold['cases']) * len(CRITERIA)} lookups but only {n_queries} distinct queries: the query is "
            "built from procedure + criterion, not the note. The first MiniLM build includes model loading."]

    # 2. End-to-end run with the production configuration.
    index = PolicyIndex(chunks, backend="minilm")
    counts = defaultdict(lambda: [0, 0, 0])            # split -> [tp, fp, fn]
    status_ok = defaultdict(lambda: [0, 0])             # split -> [correct, total]
    grounded, valid, latencies, failures, errors = [0, 0], 0, [], [], []
    for g in gold["cases"]:
        request, split = cases[g["case_id"]]
        try:
            review = review_case(request, index, args.extractor)
        except Exception as e:  # count, report, keep going
            failures.append(f"{g['case_id']}: {e!r}")
            continue
        latencies.append(review.latency_ms)
        try:
            ClinicalFacts.model_validate_json(review.facts.model_dump_json())
            valid += 1
        except ValueError as e:
            failures.append(f"{g['case_id']}: schema {e!r}")

        pred = fact_keys(review.facts)
        exp = {(field, key) for field, keys in g["expected_facts"].items() for key in keys}
        c = counts[split]
        c[0] += len(pred & exp); c[1] += len(pred - exp); c[2] += len(exp - pred)
        errors += [f"{g['case_id']} ({split}) missed fact `{f}: {k}`" for f, k in sorted(exp - pred)]
        errors += [f"{g['case_id']} ({split}) spurious fact `{f}: {k}`" for f, k in sorted(pred - exp)]

        note = norm(request.note_text)
        for r in review.checklist:
            want = g["expected_status"][r.criterion_id]
            status_ok[split][0] += r.status == want
            status_ok[split][1] += 1
            if r.status != want:
                errors.append(f"{g['case_id']} ({split}) {r.criterion_id}: expected {want}, got {r.status}. {r.explanation}")
            cited_ok = all(norm(f.evidence) in note for f in r.note_evidence)
            has_evidence = r.status == "NOT_FOUND" or any(not f.negated for f in r.note_evidence)
            grounded[0] += cited_ok and has_evidence and bool(r.policy_passages)
            grounded[1] += 1

    n = len(gold["cases"])
    out += ["", "## Extraction (field-level facts, micro-averaged)", "",
            "| Split | Precision | Recall | F1 | TP / FP / FN |", "|---|---|---|---|---|"]
    for split in ("dev", "heldout"):
        tp, fp, fn = counts[split]
        p, r, f1 = prf(tp, fp, fn)
        out.append(f"| {split} | {p:.2f} | {r:.2f} | {f1:.2f} | {tp} / {fp} / {fn} |")
    out += ["", "## Checklist, grounding, reliability", "",
            "| Metric | Value |", "|---|---|"]
    for split in ("dev", "heldout"):
        ok, total = status_ok[split]
        out.append(f"| Checklist status accuracy ({split}) | {ok}/{total} ({ok / total:.0%}) |" if total else
                   f"| Checklist status accuracy ({split}) | n/a |")
    out += [f"| Schema validity (Pydantic) | {valid}/{n} |",
            f"| Evidence grounding (cited sentence verbatim in note + policy passage attached) | {grounded[0]}/{grounded[1]} |",
            f"| Failed runs | {len(failures)}/{n} |",
            f"| Mean latency per case, excl. index build | {statistics.mean(latencies):.0f} ms |" if latencies else
            "| Mean latency | n/a |"]
    out += ["", "## Error analysis", ""] + ([f"- {e}" for e in errors + failures] or ["- No errors."])
    report = "\n".join(out) + "\n"

    (HERE / f"results_{args.extractor}.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
