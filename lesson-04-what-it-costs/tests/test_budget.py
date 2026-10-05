"""The page a manager reads. Getting a denominator wrong here is how an
estimate ends up several times under."""
from __future__ import annotations

import pytest

from src.budget import WORKING_DAYS_PER_MONTH, build_budget, price_run, sensitivity
from src.models import Usage
from src.pricing import FREE, HOSTED, LAPTOP, SMALL_SERVER


class TestPriceRun:
    def test_local_inference_costs_nothing_per_token(self, usage: Usage) -> None:
        cost = price_run("local", usage, FREE, LAPTOP)
        assert cost.input_cost == 0.0 and cost.output_cost == 0.0

    def test_a_server_charges_for_time_even_with_free_tokens(self, usage: Usage) -> None:
        """Local is not free. It is a machine you are renting by the hour."""
        cost = price_run("server", usage, FREE, SMALL_SERVER)
        assert cost.machine_cost > 0
        assert cost.total == cost.machine_cost

    def test_a_hosted_api_charges_for_tokens_and_not_for_time(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        assert cost.input_cost > 0 and cost.machine_cost == 0.0


class TestBudget:
    def _budget(self, usage: Usage, asked: int = 42, answered: int = 22):
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        return build_budget("hosted", usage, cost, asked, answered)

    def test_cost_per_answered_is_higher_than_cost_per_asked(self, usage: Usage) -> None:
        """The questions that failed still cost money. This gap is the lesson."""
        b = self._budget(usage)
        assert b.cost_per_answered > b.cost_per_question

    def test_the_gap_matches_the_answer_rate(self, usage: Usage) -> None:
        b = self._budget(usage, asked=100, answered=50)
        assert b.cost_per_answered == pytest.approx(b.cost_per_question * 2, rel=1e-3)

    def test_monthly_cost_scales_with_the_department(self, usage: Usage) -> None:
        b = self._budget(usage)
        volume = b.questions_per_adjuster_per_day * b.adjusters * WORKING_DAYS_PER_MONTH
        expected = b.cost_per_question * volume
        assert b.cost_per_month == pytest.approx(expected, rel=1e-6)

    def test_ten_times_is_ten_times(self, usage: Usage) -> None:
        b = self._budget(usage)
        assert b.cost_per_month_at_10x == pytest.approx(b.cost_per_month * 10, rel=1e-6)

    def test_latency_is_carried_into_the_budget(self, usage: Usage) -> None:
        """A cost with no latency beside it invites the wrong trade."""
        assert self._budget(usage).p95_seconds == usage.p95_seconds


class TestGuards:
    def test_zero_questions_is_rejected(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        with pytest.raises(ValueError, match="asked"):
            build_budget("x", usage, cost, 0, 0)

    def test_answering_more_than_you_asked_is_rejected(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        with pytest.raises(ValueError, match="cannot exceed"):
            build_budget("x", usage, cost, 10, 11)

    def test_answering_nothing_does_not_crash(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        assert build_budget("x", usage, cost, 10, 0).cost_per_answered == 0.0


class TestSensitivity:
    def test_the_first_row_is_what_was_measured(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        base = build_budget("hosted", usage, cost, 42, 22)
        rows = sensitivity(base)
        assert rows[0].multiplier == 1.0
        assert rows[0].cost_per_month == base.cost_per_month

    def test_an_agent_loop_is_the_biggest_single_jump(self, usage: Usage) -> None:
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        rows = sensitivity(build_budget("hosted", usage, cost, 42, 22))
        singles = [r for r in rows[1:-1]]
        assert max(singles, key=lambda r: r.multiplier).name.startswith("an agent")

    def test_combined_is_far_worse_than_any_one(self, usage: Usage) -> None:
        """The point: no single decision looks unreasonable."""
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        rows = sensitivity(build_budget("hosted", usage, cost, 42, 22))
        assert rows[-1].multiplier > 30
        assert all(r.why for r in rows)


class TestTheNumbersAgreeWithEachOther:
    """A figure a CFO cannot reproduce with a calculator is a figure you will
    spend the meeting defending instead of the proposal."""

    def _b(self, usage: Usage):
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        return build_budget("hosted", usage, cost, 42, 22)

    def test_monthly_is_exactly_per_question_times_the_volume(self, usage: Usage) -> None:
        b = self._b(usage)
        volume = b.questions_per_adjuster_per_day * b.adjusters * WORKING_DAYS_PER_MONTH
        assert b.cost_per_month == round(b.cost_per_question * volume, 2)

    def test_ten_times_is_exactly_ten_times_the_monthly(self, usage: Usage) -> None:
        b = self._b(usage)
        assert b.cost_per_month_at_10x == round(b.cost_per_month * 10, 2)
