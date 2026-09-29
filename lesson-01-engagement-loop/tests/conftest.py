"""Shared fixtures. The corpus is deterministic, so no mocking is needed anywhere."""
from __future__ import annotations

import pytest

from src.baseline import measure
from src.corpus import build_corpus, build_questions
from src.models import Claim, Document, Question
from src.search import KeywordIndex

SEED = 20260908


@pytest.fixture(scope="session")
def corpus() -> tuple[list[Claim], list[Document]]:
    return build_corpus(n_claims=200, seed=SEED)


@pytest.fixture(scope="session")
def questions(corpus) -> list[Question]:
    claims, _ = corpus
    return build_questions(claims, seed=SEED)


@pytest.fixture(scope="session")
def index(corpus) -> KeywordIndex:
    _, docs = corpus
    return KeywordIndex(docs)


@pytest.fixture(scope="session")
def measured(corpus, questions):
    _, docs = corpus
    return measure(docs, questions)
