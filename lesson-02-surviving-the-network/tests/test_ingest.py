"""End to end against a store that misbehaves. The pipeline must never raise."""
from __future__ import annotations

import pytest

from src.client import DocumentStoreClient
from src.ingest import ingest_all
from src.models import Document, IngestReport
from src.store import DocumentStore, FaultProfile


class TestHealthyRun:
    def test_it_collects_every_document(self, healthy_store: DocumentStore) -> None:
        with DocumentStoreClient(healthy_store.url) as client:
            report, documents = ingest_all(client)
        assert len(documents) == len(healthy_store.documents)
        assert report.complete is True
        assert report.acceptance_rate == 1.0

    def test_the_report_carries_the_run_id_used_in_the_logs(self, healthy_store) -> None:
        with DocumentStoreClient(healthy_store.url) as client:
            report, _ = ingest_all(client)
        assert len(report.run_id) == 36


class TestUnderFailure:
    def test_retrying_recovers_most_of_a_flaky_run(self, flaky_store: DocumentStore) -> None:
        """Half of all requests fail. Four attempts recover most, not all.

        Four straight failures at a 50% rate happens about once in sixteen, so
        across eight pages a lost page is normal. Retries buy you a much better
        run, not a guaranteed one, and the number of attempts has to suit the
        failure rate you actually see.
        """
        with DocumentStoreClient(flaky_store.url, backoff_base=0.001) as client:
            report, documents = ingest_all(client)
        assert report.retries > 0
        assert len(documents) >= 0.75 * len(flaky_store.documents)

    def test_more_attempts_recover_more(self, documents: list[Document]) -> None:
        """The relationship a reader should be able to state: attempts you can
        afford, against the failure rate you are actually seeing."""
        profile = FaultProfile(server_error_rate=0.6, seed=11)
        recovered = []
        for attempts in (1, 5):
            with DocumentStore(documents, profile, page_size=20) as store:
                with DocumentStoreClient(store.url, attempts=attempts,
                                         backoff_base=0.001) as client:
                    _, kept = ingest_all(client)
            recovered.append(len(kept))
        assert recovered[1] > recovered[0]

    def test_it_returns_a_report_instead_of_raising(self, documents: list[Document]) -> None:
        """Everything fails. The caller still gets something it can act on."""
        with DocumentStore(documents, FaultProfile(server_error_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url, attempts=2, backoff_base=0.001) as client:
                report, kept = ingest_all(client)
        assert isinstance(report, IngestReport)
        assert kept == []
        assert report.complete is False
        assert report.errors

    def test_losing_the_first_page_stops_the_run_loudly(self, documents: list[Document]) -> None:
        """Page zero is where the store says how many pages exist. Without it we
        do not know what we are missing, so we stop rather than report success."""
        with DocumentStore(documents, FaultProfile(server_error_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url, attempts=1, backoff_base=0.001) as client:
                report, _ = ingest_all(client)
        assert report.pages_fetched == 0
        assert report.complete is False
        assert "page 0" in report.errors[0]

    def test_bad_records_are_counted_not_fatal(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(invalid_record_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url) as client:
                report, kept = ingest_all(client)
        assert report.documents_rejected == store.pages
        assert report.documents_accepted == len(documents) - store.pages
        assert 0.0 < report.acceptance_rate < 1.0


class TestGuards:
    def test_zero_pages_is_rejected(self, healthy_store: DocumentStore) -> None:
        with DocumentStoreClient(healthy_store.url) as client:
            with pytest.raises(ValueError, match="max_pages"):
                ingest_all(client, max_pages=0)

    def test_max_pages_stops_early(self, healthy_store: DocumentStore) -> None:
        with DocumentStoreClient(healthy_store.url) as client:
            report, documents = ingest_all(client, max_pages=1)
        assert report.pages_fetched == 1
        assert len(documents) == 20
