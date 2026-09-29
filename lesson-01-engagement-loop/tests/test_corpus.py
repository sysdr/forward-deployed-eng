"""The corpus is the measurement instrument. If it drifts, every number moves."""
from __future__ import annotations

import re

from src.corpus import LOCATIONS, OBJECTS, _loss, build_corpus, build_questions


class TestDeterminism:
    def test_same_seed_produces_identical_corpus(self) -> None:
        a_claims, a_docs = build_corpus(n_claims=50, seed=7)
        b_claims, b_docs = build_corpus(n_claims=50, seed=7)
        assert [c.model_dump() for c in a_claims] == [c.model_dump() for c in b_claims]
        assert [d.text for d in a_docs] == [d.text for d in b_docs]

    def test_different_seed_produces_different_corpus(self) -> None:
        a, _ = build_corpus(n_claims=50, seed=7)
        b, _ = build_corpus(n_claims=50, seed=8)
        assert [c.model_dump() for c in a] != [c.model_dump() for c in b]

    def test_questions_are_deterministic(self) -> None:
        claims, _ = build_corpus(n_claims=50, seed=7)
        assert build_questions(claims, seed=7) == build_questions(claims, seed=7)


class TestGroundTruthIsUnique:
    """The bug this catches: if two claims share a loss description, a concept
    question has more than one correct answer and the accuracy number is a lie."""

    def test_loss_descriptions_are_unique_across_the_corpus(self) -> None:
        losses = [_loss(i)["doc"] for i in range(200)]
        assert len(set(losses)) == len(losses)

    def test_combination_space_exceeds_corpus_size(self) -> None:
        from src.corpus import ACTIONS

        assert len(ACTIONS) * len(LOCATIONS) * len(OBJECTS) >= 200

    def test_every_question_answer_document_exists(self) -> None:
        claims, docs = build_corpus(n_claims=200, seed=1)
        ids = {d.doc_id for d in docs}
        for q in build_questions(claims, seed=1):
            assert q.answer_doc_id in ids


class TestTheMessIsReal:
    """These assert the corpus is as awkward as a real claim file. If a future
    change tidies it up, the baseline gets easier and the lesson stops working."""

    def test_three_date_formats_appear(self) -> None:
        _, docs = build_corpus(n_claims=200, seed=3)
        notes = " ".join(d.text for d in docs if d.kind == "adjuster_notes")
        assert re.search(r"\d{4}-\d{2}-\d{2}", notes), "ISO dates missing"
        assert re.search(r"\d{2}/\d{2}/\d{4}", notes), "slash dates missing"
        assert re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", notes), "long dates missing"

    def test_some_claims_have_no_reserve(self) -> None:
        claims, _ = build_corpus(n_claims=200, seed=3)
        missing = [c for c in claims if c.reserve_amount is None]
        assert 0 < len(missing) < len(claims) * 0.4

    def test_adjuster_names_are_spelled_inconsistently(self) -> None:
        claims, _ = build_corpus(n_claims=200, seed=3)
        names = {c.adjuster for c in claims}
        assert "R. Okonkwo" in names and "R Okonkwo" in names

    def test_theft_claims_have_no_contractor_estimate(self) -> None:
        claims, docs = build_corpus(n_claims=200, seed=3)
        theft_ids = {c.claim_id for c in claims if c.peril == "theft"}
        estimates = {d.claim_id for d in docs if d.kind == "contractor_estimate"}
        assert not (theft_ids & estimates)
