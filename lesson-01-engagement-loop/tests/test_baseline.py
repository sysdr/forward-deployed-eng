"""The baseline is a number the customer will argue with. It has to be right."""
from __future__ import annotations

import pytest

from src.baseline import answer_one, measure, percentile_index
from src.models import Question


class TestPercentileIndex:
    def test_nearest_rank_on_a_small_sample(self) -> None:
        # 10 values, p90 -> round(0.9 * 9) == 8, the ninth value.
        assert percentile_index(10, 0.9) == 8
        assert percentile_index(1, 0.9) == 0
        assert percentile_index(40, 0.5) == 20

    def test_index_never_exceeds_the_sample(self) -> None:
        for n in range(1, 50):
            assert 0 <= percentile_index(n, 0.99) <= n - 1

    def test_zero_length_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            percentile_index(0, 0.5)


class TestMeasureGuards:
    def test_no_questions_is_rejected(self, corpus) -> None:
        _, docs = corpus
        with pytest.raises(ValueError, match="no questions"):
            measure(docs, [])


class TestOutcomes:
    def test_unanswerable_question_falls_back_and_is_not_found(self, index) -> None:
        """A real retrieval failure: the answer document is not in the corpus."""
        q = Question(
            question_id="Q-X",
            text="Which claim involved a meteorite strike on the conservatory?",
            answer_doc_id="C-9999-NOT",
            kind="concept",
        )
        outcome = answer_one(index, q, top_k=5)
        assert outcome.rank is None
        assert outcome.found is False
        assert outcome.seconds_to_answer == 12 * 45.0

    def test_found_question_costs_its_rank_in_reads(self, index) -> None:
        q = Question(
            question_id="Q-Y",
            text="What is the reserve amount on claim C-1042?",
            answer_doc_id="C-1042-NOT",
            kind="lookup",
        )
        outcome = answer_one(index, q, top_k=5)
        assert outcome.found is True
        assert outcome.rank is not None
        assert outcome.seconds_to_answer == outcome.rank * 45.0


class TestReportInvariants:
    def test_accuracy_is_monotonic_in_k(self, measured) -> None:
        report, _ = measured
        assert report.accuracy_at_1 <= report.accuracy_at_3 <= report.accuracy_at_5

    def test_fallback_rate_is_the_complement_of_accuracy_at_5(self, measured) -> None:
        report, _ = measured
        assert report.fallback_rate == pytest.approx(1 - report.accuracy_at_5, abs=1e-9)

    def test_one_outcome_per_question(self, measured, questions) -> None:
        _, outcomes = measured
        assert len(outcomes) == len(questions)

    def test_keyword_search_is_strong_on_identifier_lookups(self, measured) -> None:
        """The current process is not a strawman. It is already good at half the job."""
        report, _ = measured
        assert report.accuracy_lookup >= 0.90

    def test_keyword_search_is_weak_on_plain_language(self, measured) -> None:
        """And this gap is the entire reason the engagement exists."""
        report, _ = measured
        assert report.accuracy_concept < 0.40

    def test_derived_minutes_match_seconds(self, measured) -> None:
        report, _ = measured
        assert report.p50_minutes == pytest.approx(report.p50_seconds / 60, abs=0.01)
