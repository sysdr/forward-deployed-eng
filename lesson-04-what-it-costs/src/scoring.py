"""Deciding whether an answer is right.

Two scorers, and the reason there are only two is that a scorer you cannot
explain to the customer is a scorer they will not trust.

  contains  the expected string appears in the answer, ignoring case and spacing
  numeric   the expected number appears, whatever the formatting around it

Neither compares the model's prose to a reference answer. Grading prose measures
writing style and drifts the moment anyone rewords the prompt.
"""
from __future__ import annotations

import re

from src.models import EvalCase, MatchKind

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise(text: str) -> str:
    return re.sub(r"[\s,]+", "", text).lower()


def _numbers_in(text: str) -> set[str]:
    """Every number in the text, with formatting stripped and .00 removed."""
    found = set()
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace(",", "")
        if cleaned.endswith(".00"):
            cleaned = cleaned[:-3]
        found.add(cleaned.rstrip("."))
    return found


def score(case: EvalCase, answer: str) -> bool:
    """True when the answer contains the fact the question asked for."""
    if not answer.strip():
        return False
    if case.match is MatchKind.NUMERIC:
        return bool(_numbers_in(case.expected) & _numbers_in(answer))
    return _normalise(case.expected) in _normalise(answer)
