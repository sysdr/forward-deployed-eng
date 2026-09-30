"""The store is the measuring instrument. If its faults are not repeatable,
nothing measured through it is either."""
from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from src.models import Document
from src.store import DocumentStore, FaultProfile


class TestHealthyBehaviour:
    def test_serves_documents_in_pages(self, healthy_store: DocumentStore) -> None:
        body = httpx.get(f"{healthy_store.url}/documents", params={"page": 0}, timeout=5).json()
        assert body["page"] == 0
        assert len(body["documents"]) == 20
        assert body["pages"] == healthy_store.pages

    def test_every_page_is_reachable(self, healthy_store: DocumentStore) -> None:
        seen = 0
        for page in range(healthy_store.pages):
            r = httpx.get(f"{healthy_store.url}/documents", params={"page": page}, timeout=5)
            seen += len(r.json()["documents"])
        assert seen == len(healthy_store.documents)

    def test_unknown_page_is_404(self, healthy_store: DocumentStore) -> None:
        r = httpx.get(f"{healthy_store.url}/documents", params={"page": 999}, timeout=5)
        assert r.status_code == 404

    def test_non_numeric_page_is_400(self, healthy_store: DocumentStore) -> None:
        r = httpx.get(f"{healthy_store.url}/documents", params={"page": "abc"}, timeout=5)
        assert r.status_code == 400

    def test_unknown_path_is_404(self, healthy_store: DocumentStore) -> None:
        assert httpx.get(f"{healthy_store.url}/nope", timeout=5).status_code == 404


class TestFaultsAreRepeatable:
    def _statuses(self, documents: list[Document], seed: int) -> list[int]:
        profile = FaultProfile(server_error_rate=0.5, seed=seed)
        with DocumentStore(documents, profile, page_size=20) as store:
            return [
                httpx.get(f"{store.url}/documents", params={"page": 0}, timeout=5).status_code
                for _ in range(10)
            ]

    def test_same_seed_gives_the_same_failures(self, documents: list[Document]) -> None:
        assert self._statuses(documents, 3) == self._statuses(documents, 3)

    def test_different_seed_gives_different_failures(self, documents: list[Document]) -> None:
        assert self._statuses(documents, 3) != self._statuses(documents, 99)

    def test_a_failing_store_actually_fails(self, documents: list[Document]) -> None:
        assert 503 in self._statuses(documents, 3)


class TestOtherFaults:
    def test_rate_limit_carries_retry_after(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(rate_limit_rate=1.0)) as store:
            r = httpx.get(f"{store.url}/documents", params={"page": 0}, timeout=5)
            assert r.status_code == 429
            assert r.headers["Retry-After"] == "1"

    def test_malformed_body_is_a_200_that_will_not_parse(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(malformed_rate=1.0)) as store:
            r = httpx.get(f"{store.url}/documents", params={"page": 0}, timeout=5)
            assert r.status_code == 200
            with pytest.raises(json.JSONDecodeError):
                r.json()

    def test_a_hang_really_times_the_client_out(self, documents: list[Document]) -> None:
        profile = FaultProfile(timeout_rate=1.0, hang_seconds=0.5)
        with DocumentStore(documents, profile) as store:
            with pytest.raises(httpx.TimeoutException):
                httpx.get(f"{store.url}/documents", params={"page": 0}, timeout=0.3)

    def test_missing_token_is_a_permanent_403(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(), token="secret") as store:
            assert httpx.get(f"{store.url}/documents?page=0", timeout=5).status_code == 403
            ok = httpx.get(f"{store.url}/documents?page=0", timeout=5,
                           headers={"Authorization": "Bearer secret"})
            assert ok.status_code == 200

    def test_invalid_records_lose_a_required_field(self, documents: list[Document]) -> None:
        with DocumentStore(documents, FaultProfile(invalid_record_rate=1.0)) as store:
            body = httpx.get(f"{store.url}/documents?page=0", timeout=5).json()
            assert "text" not in body["documents"][0]


class TestConstruction:
    def test_page_size_must_be_positive(self, documents: list[Document]) -> None:
        with pytest.raises(ValueError, match="page_size"):
            DocumentStore(documents, page_size=0)

    def test_rates_outside_zero_to_one_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FaultProfile(server_error_rate=1.5)
