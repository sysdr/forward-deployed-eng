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
from src.guard import GuardResult, check
from src.llm import LLMClient, OllamaClient, OracleLLM
from src.loadtest import run_load
from src.meter import MeteredClient
from src.models import Budget, RunCost
from src.policy import MERIDIAN, ScopePolicy
from src.pricing import FREE, HOSTED, LAPTOP, PRICES_CHECKED, SMALL_SERVER
from src.scenarios import Kind, Scenario, all_scenarios


def _client(model: str, cases: list) -> LLMClient:
    if model == "oracle":
        return OracleLLM({c.question: c.expected for c in cases})
    return OllamaClient(model=model)


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


# ---------------------------------------------------------------------------
# Lesson 5 adds the scope guard. Everything above is carried from lesson 4
# unchanged, apart from the two new branches in main().
# ---------------------------------------------------------------------------


def is_right(scenario: Scenario, result: GuardResult) -> bool:
    """Did the guard do the right thing on this scenario?"""
    if scenario.kind is Kind.MECHANICAL:
        return scenario.expects in result.kinds()
    if scenario.kind is Kind.SCOPE_CREEP:
        return not result.allowed
    return result.allowed  # in-scope: the right answer is to let it through


def score(policy: ScopePolicy,
          scenarios: list[Scenario]) -> list[tuple[Scenario, GuardResult, bool]]:
    """Run every scenario through the guard and mark each one right or wrong."""
    rows = []
    for scenario in scenarios:
        result = check(scenario.change, policy)
        rows.append((scenario, result, is_right(scenario, result)))
    return rows


def _reported(result: GuardResult) -> str:
    return ", ".join(sorted(result.kinds())) if result.violations else "nothing"


def render(rows: list[tuple[Scenario, GuardResult, bool]]) -> str:
    """The table, then the counts, then the changes that got through."""
    out: list[str] = []
    out.append(f"{'what the agent proposed':<60} {'kind':<12} {'guard reported':<32} {'ok':>3}")
    out.append("-" * 110)
    for scenario, result, ok in rows:
        out.append(f"{scenario.change.title:<60} {scenario.kind.value:<12} "
                   f"{_reported(result):<32} {'yes' if ok else 'NO':>3}")

    mechanical = [(s, ok) for s, _, ok in rows if s.kind is Kind.MECHANICAL]
    creep = [(s, ok) for s, _, ok in rows if s.kind is Kind.SCOPE_CREEP]
    clean = [(s, ok) for s, _, ok in rows if s.kind is Kind.IN_SCOPE]
    bad = mechanical + creep

    out.append("")
    out.append(f"mechanical violations caught : {sum(1 for _, ok in mechanical if ok)}"
               f" of {len(mechanical)}")
    out.append(f"doing more than was asked    : {sum(1 for _, ok in creep if ok)} of {len(creep)}")
    out.append(f"in-scope changes allowed     : {sum(1 for _, ok in clean if ok)} of {len(clean)}")
    out.append(f"overall                      : {sum(1 for _, ok in bad if ok)} of {len(bad)}"
               " changes that should have been stopped")

    missed = [s for s, ok in bad if not ok]
    if missed:
        out.append("")
        out.append("Got through, having satisfied every written rule:")
        for scenario in missed:
            out.append("")
            out.append(f"  {scenario.change.title}")
            out.append(f"      asked for : {scenario.change.asked_for}")
            out.append(f"      why bad   : {scenario.why}")
    return "\n".join(out)


def widen(policy: ScopePolicy, path_glob: str) -> ScopePolicy:
    """The same policy with one more allowed path, and no other edit."""
    return policy.model_copy(update={"may_edit": [*policy.may_edit, path_glob]})


def guard_command(allow: str | None = None) -> None:
    policy = MERIDIAN if allow is None else widen(MERIDIAN, allow)
    print(f"Policy: {policy.engagement}")
    print(f"  may edit    {len(policy.may_edit)} path patterns")
    print(f"  never touch {len(policy.never_touch)} path patterns")
    if allow is not None:
        print(f"  widened by  may_edit += {allow!r}")
    print()
    print(render(score(policy, all_scenarios())))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the scope guard, or price the answerer.")
    parser.add_argument("--model", default="oracle")
    parser.add_argument("--budget", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--allow", default=None,
                        help="add one glob to may_edit and rescore, changing nothing else")
    args = parser.parse_args()
    if args.load:
        load_command(args.model)
    elif args.budget:
        budget_command(args.model)
    else:
        guard_command(args.allow)


if __name__ == "__main__":
    main()
