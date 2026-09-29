#!/usr/bin/env python3
"""Run the whole lesson: build the corpus, measure the baseline, write the pack.

    python -m src.main            # print the report and the scoping pack
    python -m src.main --write    # also write scoping-pack.md
"""
from __future__ import annotations

import argparse
import pathlib

from src.baseline import measure
from src.corpus import build_corpus, build_questions
from src.scope import build_scoping_pack, render


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Meridian's claim search baseline.")
    parser.add_argument("--claims", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--write", action="store_true", help="write scoping-pack.md")
    args = parser.parse_args()

    claims, documents = build_corpus(n_claims=args.claims, seed=args.seed)
    questions = build_questions(claims, seed=args.seed)
    report, outcomes = measure(documents, questions, top_k=args.top_k)

    print(f"Corpus:     {report.corpus_documents} documents across {len(claims)} claims")
    print(f"Questions:  {report.questions_asked}")
    print()
    print("Current process — keyword search over the document store")
    print(f"  answer in top 1                {report.accuracy_at_1:>7.0%}")
    print(f"  answer in top 3                {report.accuracy_at_3:>7.0%}")
    print(f"  answer in top 5                {report.accuracy_at_5:>7.0%}")
    print(f"    questions with a claim number {report.accuracy_lookup:>6.0%}")
    print(f"    questions in plain language   {report.accuracy_concept:>6.0%}")
    print()
    print(f"  median time to answer          {report.p50_minutes:>7} min")
    print(f"  p90 time to answer             {report.p90_seconds / 60:>7.2f} min")
    print(f"  mean time to answer            {report.mean_minutes:>7} min")
    print(f"  fell back to manual review     {report.fallback_rate:>7.0%}")
    print()

    pack = build_scoping_pack(report)
    markdown = render(pack, report)
    if args.write:
        out = pathlib.Path("scoping-pack.md")
        out.write_text(markdown, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
