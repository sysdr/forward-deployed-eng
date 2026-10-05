#!/usr/bin/env python3
"""Measure what the system costs.

    python -m src.main --budget                  # priced with the stub, instant
    python -m src.main --budget --model llama3.2:3b
    python -m src.main --load --model llama3.2:3b
"""
from __future__ import annotations

import argparse

from src.answerer import PROMPT, Answerer
from src.budget import build_budget, price_run, sensitivity
from src.evaluate import run_eval
from src.goldenset import build_golden_set
from src.llm import LLMClient, OllamaClient, OracleLLM, resolve_endpoint
from src.loadtest import run_load
from src.meter import MeteredClient
from src.models import Budget, RunCost
from src.pricing import FREE, HOSTED, LAPTOP, PRICES_CHECKED, SMALL_SERVER


def _client(model: str, cases: list) -> LLMClient:
    if model == "oracle":
        return OracleLLM({c.question: c.expected for c in cases})
    return OllamaClient(model=model, endpoint=resolve_endpoint())


def _show_cost(cost: RunCost) -> None:
    print(f"  {cost.label}")
    print(f"      tokens in        ${cost.input_cost:>10.4f}")
    print(f"      tokens out       ${cost.output_cost:>10.4f}")
    print(f"      machine time     ${cost.machine_cost:>10.4f}")
    print(f"      run total        ${cost.total:>10.4f}")


def _show_budget(b: Budget) -> None:
    print(f"\n  {b.label}")
    print(f"      per question asked     ${b.cost_per_question:>10.6f}")
    print(f"      per question answered  ${b.cost_per_answered:>10.6f}   <- what they are buying")
    print(f"      {b.adjusters} adjusters, {b.questions_per_adjuster_per_day} questions a day")
    print(f"      per month              ${b.cost_per_month:>10,.2f}")
    print(f"      per month at 10x       ${b.cost_per_month_at_10x:>10,.2f}")
    print(f"      p95 per question        {b.p95_seconds:>10.2f}s")


def budget_command(model: str) -> None:
    cases, documents, _ = build_golden_set()
    stable = PROMPT.split("Context:")[0]
    metered = MeteredClient(_client(model, cases), stable_prefix=stable)
    report, _ = run_eval(cases, documents, metered, label=f"cost run ({model})")
    usage = metered.usage()

    print(f"Measured on {report.cases} questions with {model}")
    print(f"  answered correctly   {report.accuracy:>7.0%}")
    print(f"  calls                {usage.calls:>7}")
    print(f"  prompt tokens        {usage.prompt_tokens:>7,}")
    print(f"  of those, cacheable  {usage.cached_prefix_tokens:>7,}")
    print(f"  completion tokens    {usage.completion_tokens:>7,}")
    print(f"  p50 / p95 seconds    {usage.p50_seconds:>7.2f} / {usage.p95_seconds:.2f}")
    print(f"\nPriced two ways (rates checked {PRICES_CHECKED}):")

    answered = round(report.accuracy * report.cases)
    local = price_run("local, on the laptop you already have", usage, FREE, LAPTOP)
    server = price_run("local, on a small always-on server", usage, FREE, SMALL_SERVER)
    hosted = price_run("a hosted API at illustrative rates", usage, HOSTED, LAPTOP)
    for cost in (local, server, hosted):
        _show_cost(cost)
    budgets = [build_budget(c.label, usage, c, report.cases, answered) for c in (server, hosted)]
    for b in budgets:
        _show_budget(b)

    print("\n  What makes the hosted bill grow, from the same measurement:")
    print(f"      {'scenario':<32}{'x':>7}{'per month':>13}")
    for row in sensitivity(budgets[-1]):
        print(f"      {row.name:<32}{row.multiplier:>7.1f}${row.cost_per_month:>12,.2f}")
    print("      none of those is an unreasonable decision on its own")


def _one_sweep(answerer: Answerer, questions: list[str], concurrency: int):
    """One row of the load table. Kept separate so the closure below binds the
    answerer it was given rather than whatever the loop last assigned."""
    return run_load(
        lambda i: answerer.answer(questions[i % len(questions)]),
        requests=12, concurrency=concurrency,
    )


def load_command(model: str, concurrencies: tuple[int, ...] = (1, 2, 4)) -> None:
    cases, documents, _ = build_golden_set()
    questions = [c.question for c in cases[:12]]
    print("One machine, more people asking at once:\n")
    print(f"  {'at once':>8}  {'p50':>7}  {'p95':>7}  {'per minute':>11}  {'errors':>7}")
    for concurrency in concurrencies:
        result = _one_sweep(Answerer(documents, _client(model, cases)), questions, concurrency)
        print(f"  {result.concurrency:>8}  {result.p50_seconds:>7.2f}  {result.p95_seconds:>7.2f}"
              f"  {result.throughput_per_minute:>11.1f}  {result.errors:>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Price the Meridian answerer.")
    parser.add_argument("--model", default="oracle")
    parser.add_argument("--budget", action="store_true")
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    if args.load:
        load_command(args.model)
    else:
        budget_command(args.model)


if __name__ == "__main__":
    main()
