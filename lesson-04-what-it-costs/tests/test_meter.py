"""Measuring cost must not mean changing the code that does the work."""
from __future__ import annotations

import pytest

from src.llm import ScriptedLLM
from src.meter import MeteredClient, percentile


class TestPercentile:
    def test_it_picks_the_nearest_rank(self) -> None:
        assert percentile([1, 2, 3, 4, 5], 0.5) == 3
        assert percentile([1, 2, 3, 4, 5], 0.95) == 5

    def test_one_value_is_its_own_percentile(self) -> None:
        assert percentile([2.5], 0.95) == 2.5

    def test_nothing_to_measure_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="nothing"):
            percentile([], 0.5)


class TestMeteredClient:
    def test_it_passes_the_answer_through_unchanged(self) -> None:
        inner = ScriptedLLM({"hello": "world"})
        metered = MeteredClient(inner)
        assert metered.complete("hello").text == inner.complete("hello").text

    def test_it_keeps_the_inner_name(self) -> None:
        assert MeteredClient(ScriptedLLM()).name == "scripted"

    def test_it_records_one_row_per_call(self) -> None:
        metered = MeteredClient(ScriptedLLM())
        for _ in range(3):
            metered.complete("anything")
        assert metered.usage().calls == 3

    def test_asking_before_measuring_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="nothing has been measured"):
            MeteredClient(ScriptedLLM()).usage()


class TestCachedPrefix:
    PREFIX = "You are helping a claims adjuster. " * 8

    def test_a_matching_prefix_is_counted(self) -> None:
        metered = MeteredClient(ScriptedLLM(), stable_prefix=self.PREFIX)
        metered.complete(self.PREFIX + "and then the question")
        assert metered.usage().cached_prefix_tokens > 0

    def test_a_prompt_that_does_not_start_with_it_counts_nothing(self) -> None:
        metered = MeteredClient(ScriptedLLM(), stable_prefix=self.PREFIX)
        metered.complete("a completely different prompt")
        assert metered.usage().cached_prefix_tokens == 0

    def test_cached_never_exceeds_the_prompt_it_came_from(self) -> None:
        """A bug here would show up as a negative bill, which nobody queries."""
        metered = MeteredClient(ScriptedLLM(), stable_prefix=self.PREFIX)
        metered.complete(self.PREFIX)
        u = metered.usage()
        assert u.cached_prefix_tokens <= u.prompt_tokens


class TestUsage:
    def test_totals_add_up(self) -> None:
        metered = MeteredClient(ScriptedLLM({"a": "one two three"}))
        metered.complete("a")
        metered.complete("a")
        u = metered.usage()
        assert u.total_tokens == u.prompt_tokens + u.completion_tokens
        assert u.mean_seconds == round(u.total_seconds / u.calls, 3)
