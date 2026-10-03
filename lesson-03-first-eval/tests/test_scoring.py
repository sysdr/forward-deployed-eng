"""Scorers decide what 'correct' means. Get these wrong and the eval lies."""
from __future__ import annotations

import pytest

from src.models import EvalCase, MatchKind
from src.scoring import score


def case(expected: str, match: MatchKind) -> EvalCase:
    return EvalCase(case_id="X", question="q", kind="lookup",
                    answer_doc_id="D", expected=expected, match=match)


class TestContains:
    def test_exact_match(self) -> None:
        assert score(case("C-1042", MatchKind.CONTAINS), "The answer is claim C-1042.")

    def test_case_and_spacing_are_ignored(self) -> None:
        assert score(case("R. Okonkwo", MatchKind.CONTAINS), "handled by r.okonkwo")

    def test_wrong_answer_fails(self) -> None:
        assert not score(case("C-1042", MatchKind.CONTAINS), "The answer is claim C-1043.")


class TestNumeric:
    def test_thousands_separators_do_not_matter(self) -> None:
        assert score(case("12,345.67", MatchKind.NUMERIC), "Reserve is 12345.67 dollars.")

    def test_trailing_zero_cents_do_not_matter(self) -> None:
        assert score(case("2,500.00", MatchKind.NUMERIC), "The deductible is 2500.")

    def test_a_different_number_fails(self) -> None:
        assert not score(case("12,345.67", MatchKind.NUMERIC), "Reserve is 12,345.68.")

    def test_prose_without_a_number_fails(self) -> None:
        assert not score(case("2,500.00", MatchKind.NUMERIC), "The deductible is stated above.")


class TestRefusals:
    @pytest.mark.parametrize("answer", ["", "   ", "\n"])
    def test_empty_answers_are_never_correct(self, answer: str) -> None:
        assert not score(case("C-1042", MatchKind.CONTAINS), answer)

    def test_a_refusal_scores_zero_on_an_answerable_case(self) -> None:
        refusal = "The context does not contain the answer."
        assert not score(case("C-1042", MatchKind.CONTAINS), refusal)

    def test_a_refusal_scores_correct_on_an_unanswerable_case(self) -> None:
        """The reserve genuinely is not set, so saying so is the right answer."""
        c = case("not yet established", MatchKind.CONTAINS)
        assert score(c, "Reserve not yet established pending inspection.")
