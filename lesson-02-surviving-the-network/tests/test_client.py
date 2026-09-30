"""The client, against a real server that really fails. No mocks anywhere."""
from __future__ import annotations

import httpx
import pytest

from src.client import DocumentStoreClient
from src.models import Document
from src.retry import RetryStats
from src.store import DocumentStore, FaultProfile


class TestHappyPath:
    def test_it_reads_a_page(self, healthy_store: DocumentStore) -> None:
        with DocumentStoreClient(healthy_store.url) as client:
            page = client.fetch_page(0)
        assert len(page.documents) == 20
        assert page.total_pages == healthy_store.pages
        assert page.rejected == {}

    def test_trailing_slash_is_trimmed(self, healthy_store: DocumentStore) -> None:
        with DocumentStoreClient(healthy_store.url + "/") as client:
            assert client.base_url == healthy_store.url


class TestRealFailures:
    def test_it_gets_through_a_flaky_server(self, flaky_store: DocumentStore) -> None:
        """Half of all requests really return 503. Retrying really fixes it."""
        stats = RetryStats()
        with DocumentStoreClient(flaky_store.url, backoff_base=0.001) as client:
            page = client.fetch_page(0, stats=stats)
        assert len(page.documents) == 20
        assert stats.retries >= 1
        assert "503" in flaky_store.stats.by_status

    def test_it_stops_immediately_on_a_bad_token(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(), token="secret") as store:
            stats = RetryStats()
            with DocumentStoreClient(store.url, backoff_base=0.001) as client:
                with pytest.raises(httpx.HTTPStatusError):
                    client.fetch_page(0, stats=stats)
            assert stats.attempts == 1          # not four
            assert stats.slept_seconds == 0.0
            assert store.stats.requests == 1    # the server was asked once

    def test_a_real_timeout_is_retried(self, documents: list[Document]) -> None:
        profile = FaultProfile(timeout_rate=1.0, hang_seconds=0.4)
        with DocumentStore(documents, profile) as store:
            stats = RetryStats()
            with DocumentStoreClient(store.url, timeout=0.15, attempts=2,
                                     backoff_base=0.001) as client:
                with pytest.raises(httpx.TimeoutException):
                    client.fetch_page(0, stats=stats)
            assert stats.retries == 1

    def test_a_truncated_body_is_retried_not_crashed(self, documents: list[Document]) -> None:
        """A 200 whose body will not parse. The usual cause is a cut connection."""
        with DocumentStore(documents, FaultProfile(malformed_rate=1.0)) as store:
            stats = RetryStats()
            with DocumentStoreClient(store.url, attempts=2, backoff_base=0.001) as client:
                with pytest.raises(httpx.ReadError):
                    client.fetch_page(0, stats=stats)
            assert stats.retries == 1

    def test_a_missing_page_is_not_retried(self, healthy_store: DocumentStore) -> None:
        stats = RetryStats()
        with DocumentStoreClient(healthy_store.url, backoff_base=0.001) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_page(999, stats=stats)
        assert stats.attempts == 1


class TestTheBoundary:
    def test_a_record_missing_a_field_is_dropped_not_fatal(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(invalid_record_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url) as client:
                page = client.fetch_page(0)
        assert len(page.documents) == 19
        assert sum(page.rejected.values()) == 1

    def test_the_rejection_names_the_field(self, documents: list[Document]) -> None:
        """"validation failed" in a log at 3am tells you nothing you can act on."""
        with DocumentStore(documents, FaultProfile(invalid_record_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url) as client:
                page = client.fetch_page(0)
        assert any(reason.startswith("text:") for reason in page.rejected)

    def test_good_records_survive_a_bad_neighbour(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(invalid_record_rate=1.0), page_size=20) as store:
            with DocumentStoreClient(store.url) as client:
                page = client.fetch_page(0)
        assert all(isinstance(d, Document) and d.text for d in page.documents)
