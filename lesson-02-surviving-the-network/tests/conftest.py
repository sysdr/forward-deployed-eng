"""Fixtures. Every test here talks to a real HTTP server on localhost."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.corpus import build_corpus
from src.models import Document
from src.store import DocumentStore, FaultProfile

SEED = 20260908


@pytest.fixture(scope="session")
def documents() -> list[Document]:
    _, docs = build_corpus(n_claims=40, seed=SEED)
    return docs


@pytest.fixture
def healthy_store(documents: list[Document]) -> Iterator[DocumentStore]:
    with DocumentStore(documents, FaultProfile(), page_size=20) as store:
        yield store


@pytest.fixture
def flaky_store(documents: list[Document]) -> Iterator[DocumentStore]:
    """Fails often enough that a single attempt will not get through."""
    profile = FaultProfile(server_error_rate=0.5, seed=7)
    with DocumentStore(documents, profile, page_size=20) as store:
        yield store
