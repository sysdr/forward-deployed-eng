#!/usr/bin/env python3
"""Run an ingest against a store that misbehaves.

    python -m src.main                    # 30% of requests fail, retries on
    python -m src.main --no-retry         # the same run without retries
    python -m src.main --demo-jitter      # what jitter does to a recovering service
"""
from __future__ import annotations

import argparse
import random
import threading
import time

from src.client import DocumentStoreClient
from src.corpus import build_corpus
from src.ingest import ingest_all
from src.models import IngestReport
from src.retry import backoff_delay
from src.store import DocumentStore, FaultProfile


def _summarise(report: IngestReport, store: DocumentStore) -> None:
    print()
    print(f"  run id               {report.run_id}")
    print(f"  pages fetched        {report.pages_fetched} of {report.pages_requested}")
    print(f"  documents kept       {report.documents_accepted}")
    print(f"  documents dropped    {report.documents_rejected}")
    for reason, count in sorted(report.rejected_reasons.items()):
        print(f"      {reason:<28} {count}")
    print(f"  http requests made   {report.http_attempts}")
    print(f"  of those, retries    {report.retries}")
    print(f"  time spent waiting   {report.slept_seconds:.2f}s")
    print(f"  wall clock           {report.duration_seconds:.2f}s")
    print(f"  server saw           {dict(sorted(store.stats.by_status.items()))}")
    print(f"  complete             {report.complete}")
    if report.errors:
        print(f"  pages lost           {len(report.errors)}")
        for e in report.errors[:3]:
            print(f"      {e}")


def _peak_arrivals(clients: int, jitter: bool) -> int:
    """Release `clients` at the same instant, then count how many land together.

    Each waits its own backoff before making one request. Without jitter every
    client waits exactly the same time, so they all arrive at once and knock over
    the service that was recovering.
    """
    peak = 0
    active = 0
    lock = threading.Lock()
    barrier = threading.Barrier(clients)

    def one(index: int) -> None:
        nonlocal peak, active
        rng = random.Random(1000 + index)
        barrier.wait()
        time.sleep(backoff_delay(3, base=0.2, jitter=jitter, rng=rng))
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)          # the request the server has to serve
        with lock:
            active -= 1

    threads = [threading.Thread(target=one, args=(i,)) for i in range(clients)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return peak


def _demo_jitter(clients: int = 40) -> None:
    """Every client fails at the same instant. Do they come back together?"""
    print("Every client fails at once, then retries. Peak load on the way back:")
    for jitter, label in ((False, "without jitter"), (True, "with jitter   ")):
        peak = _peak_arrivals(clients, jitter)
        print(f"  {label}  {peak} of {clients} clients arrive together")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest from a store that fails.")
    parser.add_argument("--claims", type=int, default=200)
    parser.add_argument("--fail-rate", type=float, default=0.30)
    parser.add_argument("--no-retry", action="store_true", help="one attempt per page")
    parser.add_argument("--demo-jitter", action="store_true")
    args = parser.parse_args()

    if args.demo_jitter:
        _demo_jitter()
        return

    _, documents = build_corpus(n_claims=args.claims)
    profile = FaultProfile(
        server_error_rate=args.fail_rate * 0.5,
        rate_limit_rate=args.fail_rate * 0.2,
        malformed_rate=args.fail_rate * 0.2,
        invalid_record_rate=args.fail_rate * 0.3,
    )
    attempts = 1 if args.no_retry else 4

    print(f"Store failing about {args.fail_rate:.0%} of requests, "
          f"{'no retries' if args.no_retry else f'{attempts} attempts per page'}")
    with DocumentStore(documents, profile) as store:
        with DocumentStoreClient(store.url, attempts=attempts) as client:
            report, kept = ingest_all(client)
        _summarise(report, store)
    print(f"\n  {len(kept)} of {len(documents)} documents made it through.")


if __name__ == "__main__":
    main()
