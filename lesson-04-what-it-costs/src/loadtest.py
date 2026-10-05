"""What happens when more than one adjuster asks at once.

A latency you measured one question at a time is the best number your system
will ever produce. The number that matters is the one under the load the
customer actually has, and on a single machine it gets worse quickly.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from src.meter import percentile


class LoadResult(BaseModel):
    concurrency: int
    requests: int
    p50_seconds: float
    p95_seconds: float
    wall_seconds: float
    throughput_per_minute: float
    errors: int


def run_load(
    work: Callable[[int], Any],
    requests: int = 12,
    concurrency: int = 1,
) -> LoadResult:
    """Run `work` `requests` times, `concurrency` at a time, and time each one.

    Whatever `work` returns is discarded. Only how long it took matters here.
    """
    if requests < 1 or concurrency < 1:
        raise ValueError("requests and concurrency must both be at least 1")

    timings: list[float] = []
    errors = 0
    lock = threading.Lock()
    gate = threading.Semaphore(concurrency)
    started = time.monotonic()

    def one(index: int) -> None:
        nonlocal errors
        with gate:
            begin = time.monotonic()
            try:
                work(index)
            except Exception:  # noqa: BLE001 - counted, and the run continues
                with lock:
                    errors += 1
                return
            finally:
                elapsed = time.monotonic() - begin
            with lock:
                timings.append(elapsed)

    threads = [threading.Thread(target=one, args=(i,)) for i in range(requests)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    wall = time.monotonic() - started
    return LoadResult(
        concurrency=concurrency,
        requests=requests,
        p50_seconds=percentile(timings, 0.50) if timings else 0.0,
        p95_seconds=percentile(timings, 0.95) if timings else 0.0,
        wall_seconds=round(wall, 3),
        throughput_per_minute=round(len(timings) / wall * 60, 1) if wall else 0.0,
        errors=errors,
    )
