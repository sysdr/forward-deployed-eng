"""What happens when more than one person asks at once."""
from __future__ import annotations

import threading
import time

import pytest

from src.loadtest import run_load


class TestGuards:
    def test_zero_requests_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            run_load(lambda i: None, requests=0)

    def test_zero_concurrency_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            run_load(lambda i: None, requests=4, concurrency=0)


class TestMeasurement:
    def test_every_request_is_timed(self) -> None:
        result = run_load(lambda i: time.sleep(0.01), requests=6, concurrency=2)
        assert result.requests == 6
        assert result.p50_seconds >= 0.01
        assert result.errors == 0

    def test_running_them_at_once_finishes_sooner(self) -> None:
        serial = run_load(lambda i: time.sleep(0.05), requests=6, concurrency=1)
        parallel = run_load(lambda i: time.sleep(0.05), requests=6, concurrency=6)
        assert parallel.wall_seconds < serial.wall_seconds
        assert parallel.throughput_per_minute > serial.throughput_per_minute

    def test_concurrency_is_actually_limited(self) -> None:
        """If the semaphore were wrong, the whole load test would be a lie."""
        peak = 0
        active = 0
        lock = threading.Lock()

        def work(_: int) -> None:
            nonlocal peak, active
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1

        run_load(work, requests=12, concurrency=3)
        assert peak <= 3


class TestFailures:
    def test_a_failing_request_is_counted_not_fatal(self) -> None:
        def sometimes(i: int) -> None:
            if i % 3 == 0:
                raise RuntimeError("upstream said no")

        result = run_load(sometimes, requests=9, concurrency=2)
        assert result.errors == 3
        assert result.requests == 9

    def test_everything_failing_still_returns_a_result(self) -> None:
        result = run_load(lambda i: (_ for _ in ()).throw(RuntimeError("no")), requests=4)
        assert result.errors == 4
        assert result.p95_seconds == 0.0
