"""The golden set is the specification. If it is wrong, every number is wrong."""
from __future__ import annotations

from src.goldenset import build_golden_set
from src.models import MatchKind


class TestShape:
    def test_one_case_per_question(self, cases) -> None:
        assert len(cases) == 42          # 40 sampled + 2 curated edge cases
        assert len({c.case_id for c in cases}) == 42

    def test_every_answer_document_exists(self, cases, documents) -> None:
        ids = {d.doc_id for d in documents} | {"__none__"}
        assert all(c.answer_doc_id in ids for c in cases)

    def test_both_kinds_are_present(self, cases) -> None:
        kinds = {c.kind for c in cases}
        assert kinds == {"lookup", "concept"}

    def test_deterministic(self) -> None:
        a, _, _ = build_golden_set(n_claims=60, seed=11)
        b, _, _ = build_golden_set(n_claims=60, seed=11)
        assert [c.model_dump() for c in a] == [c.model_dump() for c in b]


class TestExpectedFacts:
    def test_concept_cases_expect_a_claim_identifier(self, cases) -> None:
        for c in (c for c in cases if c.kind == "concept"):
            assert c.expected.startswith("C-")
            assert c.match is MatchKind.CONTAINS

    def test_expected_fact_is_actually_in_its_document(self, cases, documents) -> None:
        """Guards the whole exercise: an expected answer that is not in the
        document makes the case unanswerable and quietly caps your score."""
        text = {d.doc_id: d.text for d in documents}
        for c in cases:
            if c.answer_doc_id == "__none__":
                continue  # the refusal case has no document by design
            body = text[c.answer_doc_id].replace(",", "").lower()
            assert c.expected.replace(",", "").lower() in body, c.case_id

    def test_the_unset_reserve_case_is_present(self, cases) -> None:
        """Random sampling missed this entirely. It is added deliberately."""
        assert [c for c in cases if c.expected == "not yet established"]

    def test_the_nonexistent_claim_case_is_present(self, cases) -> None:
        """A question with no answer anywhere. Only a refusal is correct."""
        refusal = [c for c in cases if c.answer_doc_id == "__none__"]
        assert len(refusal) == 1
        assert "does not contain" in refusal[0].expected
