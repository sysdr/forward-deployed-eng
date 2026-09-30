"""Which failures are worth another go, and what the waiting costs."""
from __future__ import annotations

import random

import httpx
import pytest

from src.retry import RetryStats, backoff_delay, is_worth_retrying, with_retry


def status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://example.invalid/documents")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"{code}", request=request, response=response)


class TestClassification:
    @pytest.mark.parametrize("code", [500, 502, 503, 504, 429])
    def test_server_trouble_and_rate_limits_are_worth_retrying(self, code: int) -> None:
        assert is_worth_retrying(status_error(code))

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
    def test_a_bad_request_is_never_worth_retrying(self, code: int) -> None:
        assert not is_worth_retrying(status_error(code))

    def test_timeouts_are_worth_retrying(self) -> None:
        assert is_worth_retrying(httpx.ReadTimeout("slow"))

    def test_refused_connections_are_worth_retrying(self) -> None:
        assert is_worth_retrying(httpx.ConnectError("refused"))

    def test_a_programming_mistake_is_not_retried(self) -> None:
        """A KeyError will be a KeyError next time too."""
        assert not is_worth_retrying(KeyError("oops"))


class TestBackoff:
    def test_delay_doubles(self) -> None:
        assert backoff_delay(1, base=1.0, jitter=False) == 1.0
        assert backoff_delay(2, base=1.0, jitter=False) == 2.0
        assert backoff_delay(3, base=1.0, jitter=False) == 4.0

    def test_delay_is_capped(self) -> None:
        assert backoff_delay(20, base=1.0, cap=5.0, jitter=False) == 5.0

    def test_attempt_zero_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="attempt"):
            backoff_delay(0)

    def test_jitter_spreads_clients_apart(self) -> None:
        """Without it, everyone who failed together comes back together."""
        flat = {backoff_delay(3, base=1.0, jitter=False) for _ in range(50)}
        spread = {backoff_delay(3, base=1.0, jitter=True, rng=random.Random(i)) for i in range(50)}
        assert len(flat) == 1
        assert len(spread) > 40

    def test_jitter_stays_within_half_and_one_and_a_half(self) -> None:
        for i in range(200):
            d = backoff_delay(2, base=1.0, jitter=True, rng=random.Random(i))
            assert 1.0 <= d <= 3.0


class TestWithRetry:
    def test_a_call_that_works_is_not_retried(self) -> None:
        stats = RetryStats()
        assert with_retry(lambda: "ok", stats=stats, sleep=lambda _: None) == "ok"
        assert stats.attempts == 1
        assert stats.retries == 0

    def test_it_succeeds_after_a_wobble(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise status_error(503)
            return "ok"

        stats = RetryStats()
        assert with_retry(flaky, stats=stats, sleep=lambda _: None) == "ok"
        assert stats.attempts == 3
        assert stats.retries == 2

    def test_a_403_fails_on_the_first_attempt(self) -> None:
        """The point of the whole lesson: no waiting, no wasted quota."""
        stats = RetryStats()
        with pytest.raises(httpx.HTTPStatusError):
            with_retry(lambda: (_ for _ in ()).throw(status_error(403)),
                       stats=stats, sleep=lambda _: None)
        assert stats.attempts == 1
        assert stats.slept_seconds == 0.0
        assert stats.gave_up_permanent == 1

    def test_it_eventually_gives_up(self) -> None:
        stats = RetryStats()
        with pytest.raises(httpx.HTTPStatusError):
            with_retry(lambda: (_ for _ in ()).throw(status_error(503)),
                       attempts=3, stats=stats, sleep=lambda _: None)
        assert stats.attempts == 3
        assert stats.gave_up_exhausted == 1

    def test_zero_attempts_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="attempts"):
            with_retry(lambda: "x", attempts=0)

    def test_waiting_is_recorded(self) -> None:
        stats = RetryStats()
        with pytest.raises(httpx.HTTPStatusError):
            with_retry(lambda: (_ for _ in ()).throw(status_error(503)),
                       attempts=3, base=1.0, jitter=False, stats=stats, sleep=lambda _: None)
        assert stats.delays == [1.0, 2.0]
        assert stats.slept_seconds == 3.0
