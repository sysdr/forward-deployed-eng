"""Counting what every model call spends.

Wrap any client and it keeps working exactly as before, while recording tokens
and seconds. Measuring cost should never mean changing the code that does the
work, or you will stop measuring the moment it is inconvenient.
"""
from __future__ import annotations

from src.llm import LLMClient
from src.models import CallRecord, Completion, Usage


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile on a small sample, clamped."""
    if not values:
        raise ValueError("cannot take a percentile of nothing")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return round(ordered[index], 3)


class MeteredClient:
    """An LLMClient that also remembers what it spent.

    `cached_prefix_tokens` is the length of a leading section of the prompt that
    is identical every time. Providers that bill cached input cheaply charge less
    for it, so a system that sends a long stable prefix and a short variable tail
    can cost less than one sending a short prompt built fresh each call.
    """

    def __init__(self, inner: LLMClient, stable_prefix: str = "") -> None:
        self.inner = inner
        self.name = inner.name
        self.stable_prefix = stable_prefix
        self.records: list[CallRecord] = []

    def complete(self, prompt: str) -> Completion:
        completion = self.inner.complete(prompt)
        cached = 0
        if self.stable_prefix and prompt.startswith(self.stable_prefix):
            # Roughly four characters per token is close enough to compare two
            # designs. It is not close enough to put on an invoice.
            cached = len(self.stable_prefix) // 4
        self.records.append(
            CallRecord(
                prompt_tokens=completion.prompt_tokens,
                completion_tokens=completion.completion_tokens,
                seconds=completion.seconds,
                cached_prefix_tokens=min(cached, completion.prompt_tokens),
            )
        )
        return completion

    def usage(self) -> Usage:
        if not self.records:
            raise ValueError("nothing has been measured yet")
        seconds = [r.seconds for r in self.records]
        return Usage(
            calls=len(self.records),
            prompt_tokens=sum(r.prompt_tokens for r in self.records),
            completion_tokens=sum(r.completion_tokens for r in self.records),
            cached_prefix_tokens=sum(r.cached_prefix_tokens for r in self.records),
            total_seconds=round(sum(seconds), 3),
            p50_seconds=percentile(seconds, 0.50),
            p95_seconds=percentile(seconds, 0.95),
        )
