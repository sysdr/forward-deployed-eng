"""Trying again, but only when trying again could work.

The whole idea fits in one sentence: some failures go away on their own and some
never will, and the difference decides whether waiting helps or just wastes the
customer's afternoon.

  Worth another go   503, 502, 504, 429, a dropped connection, a timeout
  Never worth it     400, 401, 403, 404 — the request itself is wrong

Retrying a 403 three times takes seven seconds, uses three of your rate limit, and
ends exactly where it started.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

import httpx

from src.obs import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

PERMANENT_STATUS = frozenset({400, 401, 403, 404, 405, 409, 410, 422})


def is_worth_retrying(exc: Exception) -> bool:
    """True when waiting and trying again could plausibly succeed."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code not in PERMANENT_STATUS
    # Timeouts, refused connections, resets. The request never got an answer.
    return isinstance(exc, httpx.TransportError)


@dataclass
class RetryStats:
    """What the retrying actually cost, so the article can quote a number."""

    attempts: int = 0
    retries: int = 0
    slept_seconds: float = 0.0
    gave_up_permanent: int = 0
    gave_up_exhausted: int = 0
    delays: list[float] = field(default_factory=list)


def backoff_delay(
    attempt: int,
    base: float = 0.2,
    cap: float = 5.0,
    factor: float = 2.0,
    jitter: bool = True,
    rng: random.Random | None = None,
) -> float:
    """Seconds to wait before attempt number `attempt` + 1.

    Doubling alone makes every client that failed together retry together. The
    random multiplier spreads them out, which is the difference between a
    recovering service and one that gets knocked over again.
    """
    if attempt < 1:
        raise ValueError("attempt starts at 1")
    delay = min(base * (factor ** (attempt - 1)), cap)
    if jitter:
        source = rng or random
        delay *= 0.5 + source.random()
    return delay


def with_retry[T](
    call: Callable[[], T],
    attempts: int = 4,
    base: float = 0.2,
    cap: float = 5.0,
    jitter: bool = True,
    stats: RetryStats | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    """Run `call`, retrying only the failures that are worth retrying.

    Raises the last exception if it never succeeds. Callers that must not raise
    wrap this, rather than swallowing it here.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    record = stats or RetryStats()
    last: Exception | None = None

    for attempt in range(1, attempts + 1):
        record.attempts += 1
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - classified immediately below
            last = exc
            if not is_worth_retrying(exc):
                record.gave_up_permanent += 1
                logger.error(
                    "giving up, retrying cannot help",
                    extra={"attempt": attempt, "reason": type(exc).__name__,
                           "detail": str(exc)[:200]},
                )
                raise
            if attempt == attempts:
                record.gave_up_exhausted += 1
                logger.error(
                    "giving up, out of attempts",
                    extra={"attempts": attempts, "reason": type(exc).__name__,
                           "detail": str(exc)[:200]},
                )
                raise
            delay = backoff_delay(attempt, base, cap, jitter=jitter, rng=rng)
            record.retries += 1
            record.slept_seconds += delay
            record.delays.append(round(delay, 3))
            logger.warning(
                "trying again",
                extra={"attempt": attempt, "waiting_seconds": round(delay, 3),
                       "reason": type(exc).__name__},
            )
            sleep(delay)

    raise last if last else RuntimeError("unreachable")
