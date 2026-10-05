"""Fixtures. Nothing here calls a model."""
from __future__ import annotations

import pytest

from src.goldenset import build_golden_set
from src.llm import OracleLLM
from src.models import Usage

SEED = 20260908


@pytest.fixture(scope="session")
def golden():
    return build_golden_set(n_claims=200, seed=SEED)


@pytest.fixture(scope="session")
def cases(golden):
    return golden[0]


@pytest.fixture(scope="session")
def documents(golden):
    return golden[1]


@pytest.fixture
def oracle(cases):
    return OracleLLM({c.question: c.expected for c in cases})


@pytest.fixture
def usage() -> Usage:
    """A measured run, made up but shaped like a real one."""
    return Usage(
        calls=42, prompt_tokens=800_000, completion_tokens=20_000,
        cached_prefix_tokens=200_000, total_seconds=60.0,
        p50_seconds=1.4, p95_seconds=2.9,
    )
