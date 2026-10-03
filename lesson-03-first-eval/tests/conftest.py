"""Fixtures. Nothing here touches a model or the network."""
from __future__ import annotations

import pytest

from src.goldenset import build_golden_set
from src.llm import OracleLLM
from src.models import Claim, Document, EvalCase

SEED = 20260908


@pytest.fixture(scope="session")
def golden() -> tuple[list[EvalCase], list[Document], list[Claim]]:
    return build_golden_set(n_claims=200, seed=SEED)


@pytest.fixture(scope="session")
def cases(golden) -> list[EvalCase]:
    return golden[0]


@pytest.fixture(scope="session")
def documents(golden) -> list[Document]:
    return golden[1]


@pytest.fixture
def oracle(cases) -> OracleLLM:
    return OracleLLM({c.question: c.expected for c in cases})
