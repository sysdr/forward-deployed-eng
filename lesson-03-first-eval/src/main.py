#!/usr/bin/env python3
"""Run the golden set.

    python -m src.main --model oracle          # the ceiling retrieval allows
    python -m src.main --model llama3.1:8b     # a model on OLLAMA_HOST
    python -m src.main --model oracle --save-baseline
    python -m src.main --model oracle --gate   # exits 1 on regression
"""
from __future__ import annotations

import argparse

from src.evaluate import compare_to_baseline, load_baseline, run_eval, save_baseline
from src.goldenset import build_golden_set
from src.llm import LLMClient, OllamaClient, OracleLLM, resolve_endpoint
from src.models import EvalReport


def _print(report: EvalReport) -> None:
    print(f"  model                {report.model}")
    print(f"  cases                {report.cases}")
    print(f"  answer in context    {report.retrieval_hit_rate:>7.0%}"
          "   <- retrieval, answerable only")
    print(f"  answered correctly   {report.accuracy:>7.0%}   <- the whole system")
    lookup = f"{report.accuracy_lookup:>7.0%}" if report.lookup_cases else "    n/a"
    concept = f"{report.accuracy_concept:>7.0%}" if report.concept_cases else "    n/a"
    print(f"    with a claim number{lookup}")
    print(f"    plain language     {concept}")
    print(f"  lost after retrieval {report.headroom:>7.1%}   <- the model's share")
    print(f"  mean seconds/case    {report.mean_seconds:>7.2f}")
    print(f"  completion tokens    {report.total_completion_tokens:>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Meridian golden set.")
    parser.add_argument(
        "--model", default="oracle",
        help="'oracle' for the retrieval ceiling, or an Ollama model name",
    )
    parser.add_argument("--limit", type=int, default=0, help="run only the first N cases")
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="documents given to the model. Lower it to degrade retrieval on purpose.",
    )
    parser.add_argument("--claims", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--gate", action="store_true", help="fail on regression")
    args = parser.parse_args()

    cases, documents, _ = build_golden_set(n_claims=args.claims, seed=args.seed)
    if args.limit:
        cases = cases[: args.limit]

    client: LLMClient
    if args.model == "oracle":
        client = OracleLLM({c.question: c.expected for c in cases})
        label = "oracle (retrieval ceiling)"
    else:
        client = OllamaClient(model=args.model, endpoint=resolve_endpoint())
        label = f"local model {args.model}"

    print(f"Golden set — {label}")
    report, _ = run_eval(cases, documents, client, label=label, top_k=args.top_k)
    _print(report)

    if args.save_baseline:
        save_baseline(report)
        print("\n  baseline written to evals/baseline.json")
        return

    if args.gate:
        baseline = load_baseline()
        if baseline is None:
            print("\n  no baseline yet — run with --save-baseline")
            raise SystemExit(1)
        regressions = compare_to_baseline(report, baseline)
        if regressions:
            print("\n  REGRESSION")
            for r in regressions:
                print(f"    {r.metric}: {r.baseline:.0%} -> {r.current:.0%}  (down {r.drop:.0%})")
            raise SystemExit(1)
        print("\n  no regression against evals/baseline.json")


if __name__ == "__main__":
    main()
