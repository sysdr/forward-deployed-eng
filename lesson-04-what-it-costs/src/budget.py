"""Turning a measured run into the page a manager reads.

Everything here is division. The care is in choosing the denominator, and the
denominator that matters is a unit of the customer's work, not a unit of yours.
Cost per thousand tokens means nothing to the VP of Claims. Cost per claim
question does.
"""
from __future__ import annotations

from pydantic import BaseModel

from src.models import Budget, RunCost, Usage
from src.pricing import MachinePrice, TokenPrice

WORKING_DAYS_PER_MONTH = 21


def price_run(label: str, usage: Usage, tokens: TokenPrice, machine: MachinePrice) -> RunCost:
    """What one run of the golden set costs on a given way of running it."""
    input_cost, output_cost = tokens.cost(
        usage.prompt_tokens, usage.completion_tokens, usage.cached_prefix_tokens
    )
    return RunCost(
        label=label,
        input_cost=input_cost,
        output_cost=output_cost,
        machine_cost=machine.cost(usage.total_seconds),
    )


def build_budget(
    label: str,
    usage: Usage,
    run_cost: RunCost,
    asked: int,
    answered: int,
    questions_per_adjuster_per_day: int = 18,
    adjusters: int = 120,
) -> Budget:
    """Scale one measured run up to a month of a claims department.

    Two costs per question, and the gap between them is the point. The first
    divides by every question asked. The second divides by the ones that got a
    useful answer, which is what the customer is actually buying.
    """
    if asked < 1:
        raise ValueError("asked must be at least 1")
    if answered > asked:
        raise ValueError("answered cannot exceed asked")

    # Round once, here, and derive everything else from the rounded figure.
    # If the monthly number is computed from more decimal places than you
    # printed, nobody can reproduce it with a calculator, and you will spend the
    # meeting defending arithmetic instead of the proposal.
    per_question = round(run_cost.total / asked, 6)
    per_answered = round(run_cost.total / answered, 6) if answered else 0.0
    monthly_questions = questions_per_adjuster_per_day * adjusters * WORKING_DAYS_PER_MONTH

    return Budget(
        label=label,
        asked=asked,
        answered=answered,
        cost_per_question=per_question,
        cost_per_answered=per_answered,
        questions_per_adjuster_per_day=questions_per_adjuster_per_day,
        adjusters=adjusters,
        cost_per_month=round(per_question * monthly_questions, 2),
        cost_per_month_at_10x=round(round(per_question * monthly_questions, 2) * 10, 2),
        p95_seconds=usage.p95_seconds,
    )


class Scenario(BaseModel):
    """One way the bill grows after the pilot."""

    name: str
    multiplier: float
    cost_per_month: float
    why: str


def sensitivity(base: Budget) -> list[Scenario]:
    """What turns a trivial bill into the one that cancels the project.

    The per-question cost of a single model call is small enough to be ignored,
    and that is exactly why teams are surprised later. Nothing below is exotic.
    Each is an ordinary design decision taken after the pilot was approved.
    """
    rows = [
        ("as measured today", 1.0,
         "one retrieval, one model call, short answers"),
        ("an agent that takes 8 steps", 8.0,
         "the same question, planned and re-checked, is eight calls not one"),
        ("ten times the context", 3.5,
         "more documents retrieved per question; output stays about the same"),
        ("retries on a flaky quarter", 1.25,
         "lesson 2's retry policy, applied to a bad month"),
        ("all three together", 8.0 * 3.5 * 1.25,
         "none of these decisions is unreasonable on its own"),
    ]
    return [
        Scenario(name=name, multiplier=round(m, 2),
                 cost_per_month=round(base.cost_per_month * m, 2), why=why)
        for name, m, why in rows
    ]
