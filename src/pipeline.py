"""End-to-end pipeline and command-line demo.

    python -m src.pipeline PA-001                 # Markdown report
    python -m src.pipeline PA-003 --json          # full Review as JSON
    python -m src.pipeline PA-001 --extractor llm # Claude extraction (needs ANTHROPIC_API_KEY)
"""
import argparse
import os
import sys
import time

from .assessment import assess, follow_up_questions
from .extraction import extract
from .ingestion import load_cases, load_policies
from .reporting import to_markdown
from .retrieval import PolicyIndex
from .schemas import CaseRequest, Review

DEFAULT_BACKEND = os.getenv("EMBEDDING_BACKEND", "minilm")


def build_index(backend: str = DEFAULT_BACKEND) -> PolicyIndex:
    return PolicyIndex(load_policies(), backend=backend)


def review_case(request: CaseRequest, index: PolicyIndex, extractor: str = "rules", client=None) -> Review:
    start = time.perf_counter()
    facts = extract(request, extractor, client)
    checklist = assess(facts, request, index)
    return Review(request=request, facts=facts, checklist=checklist,
                  follow_up_questions=follow_up_questions(checklist, request),
                  extractor=extractor, retriever=index.backend,
                  latency_ms=(time.perf_counter() - start) * 1000)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # report uses emoji; Windows consoles default to cp1252
    cases = {req.case_id: req for req, _ in load_cases()}
    parser = argparse.ArgumentParser(description="Prior-authorization review copilot (synthetic demo)")
    parser.add_argument("case_id", choices=sorted(cases))
    parser.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    parser.add_argument("--backend", choices=["minilm", "tfidf"], default=DEFAULT_BACKEND)
    parser.add_argument("--json", action="store_true", help="print the full Review JSON instead of Markdown")
    args = parser.parse_args(argv)

    review = review_case(cases[args.case_id], build_index(args.backend), args.extractor)
    print(review.model_dump_json(indent=2) if args.json else to_markdown(review))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
