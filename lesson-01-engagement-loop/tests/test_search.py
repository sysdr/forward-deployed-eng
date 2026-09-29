"""Tests for the current-process search, including the ways it genuinely fails."""
from __future__ import annotations

import pytest

from src.models import DocKind, Document
from src.search import KeywordIndex, tokenize


class TestTokenize:
    def test_claim_identifiers_survive_as_one_token(self) -> None:
        assert "c-1042" in tokenize("What is the reserve on claim C-1042?")

    def test_stopwords_and_domain_noise_are_dropped(self) -> None:
        tokens = tokenize("What is the claim policy for this")
        assert tokens == []

    def test_punctuation_does_not_create_tokens(self) -> None:
        assert tokenize("!!! ??? ...") == []


class TestIndexConstruction:
    def test_empty_corpus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="zero documents"):
            KeywordIndex([])


class TestSearchFailureModes:
    """Every one of these is a real failure, not a mocked one."""

    @pytest.fixture
    def tiny(self) -> KeywordIndex:
        return KeywordIndex(
            [
                Document(
                    doc_id="A", claim_id="C-1", kind=DocKind.NOTES,
                    text="burst pipe upstairs",
                ),
                Document(
                    doc_id="B", claim_id="C-2", kind=DocKind.NOTES,
                    text="storm damaged roof",
                ),
            ]
        )

    def test_query_of_only_stopwords_returns_nothing(self, tiny: KeywordIndex) -> None:
        assert tiny.search("what is the this that") == []

    def test_query_matching_no_document_returns_nothing(self, tiny: KeywordIndex) -> None:
        assert tiny.search("earthquake subsidence") == []

    def test_invalid_top_k_is_rejected(self, tiny: KeywordIndex) -> None:
        with pytest.raises(ValueError, match="top_k"):
            tiny.search("pipe", top_k=0)

    def test_top_k_larger_than_corpus_is_safe(self, tiny: KeywordIndex) -> None:
        assert len(tiny.search("pipe roof", top_k=500)) <= 2


class TestRanking:
    def test_identifier_lookup_retrieves_the_right_claim(self, index) -> None:
        hits = index.search("What is the reserve amount on claim C-1042?", top_k=5)
        # The identifier dominates the ranking, so the named claim takes the top
        # slots. The tail is noise from "reserve" matching other claims' notes.
        assert hits[0].doc_id.startswith("C-1042")
        assert "C-1042-NOT" in [h.doc_id for h in hits]

    def test_short_documents_outrank_long_ones_on_the_same_term(self, index) -> None:
        """A real bias in the instrument, not a bug in the corpus.

        Term frequency is divided by document length, so a 20-word photo
        manifest scores higher on `c-1042` than a 60-word set of adjuster
        notes containing the same identifier once. This is why accuracy at 1
        is far below accuracy at 5 in the baseline report, and it is the
        reason length-normalised ranking exists. Lesson 12 replaces this.
        """
        hits = index.search("claim C-1042", top_k=5)
        ranks = {h.doc_id: i for i, h in enumerate(hits)}
        assert ranks["C-1042-PHO"] < ranks["C-1042-NOT"]

    def test_results_are_ordered_by_descending_score(self, index) -> None:
        hits = index.search("burst pipe upstairs bathroom", top_k=5)
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)

    def test_ties_break_deterministically_across_runs(self, corpus) -> None:
        _, docs = corpus
        a = KeywordIndex(docs).search("photo manifest images captured", top_k=10)
        b = KeywordIndex(docs).search("photo manifest images captured", top_k=10)
        assert [h.doc_id for h in a] == [h.doc_id for h in b]
