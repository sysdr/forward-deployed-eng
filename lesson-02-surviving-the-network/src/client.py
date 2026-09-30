"""The one place this program touches another company's service.

Everything that can go wrong with someone else's network is handled here, so the
rest of the code can be written as though data simply arrives.

Two jobs. Ask for a page, retrying the failures worth retrying. And check what came
back before letting it any further in, because a service that has been running for
a decade will eventually hand you a record with a missing field, and the moment to
find out is now, not three functions later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from src.models import Document
from src.obs import get_logger
from src.retry import RetryStats, with_retry

logger = get_logger(__name__)


@dataclass
class Page:
    """One page of documents, plus the ones that did not survive checking."""

    index: int
    total_pages: int
    documents: list[Document]
    rejected: dict[str, int]


class DocumentStoreClient:
    """Reads documents from the store over HTTP."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        attempts: int = 4,
        token: str | None = None,
        jitter: bool = True,
        backoff_base: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.attempts = attempts
        self.jitter = jitter
        # Tests drop this to near zero so the suite stays fast.
        self.backoff_base = backoff_base
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.Client(timeout=timeout, headers=headers)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> DocumentStoreClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_page(self, index: int, stats: RetryStats | None = None) -> Page:
        """Fetch one page. Raises if it never succeeds."""

        def call() -> dict[str, object]:
            response = self._http.get(f"{self.base_url}/documents", params={"page": index})
            response.raise_for_status()
            try:
                body: dict[str, object] = response.json()
            except json.JSONDecodeError as exc:
                # A 200 with a body we cannot read. Worth another go, because the
                # usual cause is a connection cut mid-response.
                raise httpx.ReadError(f"unreadable body from page {index}: {exc}") from exc
            return body

        body = with_retry(
            call, attempts=self.attempts, base=self.backoff_base,
            stats=stats, jitter=self.jitter,
        )
        return self._validate(index, body)

    def _validate(self, index: int, body: dict[str, object]) -> Page:
        """Turn raw records into Documents, counting whatever will not convert."""
        raw = body.get("documents")
        if not isinstance(raw, list):
            raise httpx.ReadError(f"page {index} had no documents list")

        documents: list[Document] = []
        rejected: dict[str, int] = {}
        for record in raw:
            try:
                documents.append(Document.model_validate(record))
            except ValidationError as exc:
                # Name the field that was wrong. "validation failed" in a log at
                # 3am tells you nothing you can act on.
                field = ".".join(str(p) for p in exc.errors()[0]["loc"]) or "unknown"
                reason = f"{field}: {exc.errors()[0]['type']}"
                rejected[reason] = rejected.get(reason, 0) + 1
                doc_id = record.get("doc_id") if isinstance(record, dict) else None
                logger.warning(
                    "record rejected at the boundary",
                    extra={"page": index, "reason": reason, "doc_id": doc_id},
                )

        total = body.get("pages")
        return Page(
            index=index,
            total_pages=int(total) if isinstance(total, int) else 1,
            documents=documents,
            rejected=rejected,
        )
