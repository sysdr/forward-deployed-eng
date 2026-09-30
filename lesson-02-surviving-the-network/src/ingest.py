"""Pull every page, keep what is valid, and never raise.

The caller of a pipeline cannot do anything useful with a traceback. It can do
something with a report that says four of fifteen pages never arrived and here is
the run identifier to search for. So failures come back as data.
"""
from __future__ import annotations

import time

from src.client import DocumentStoreClient
from src.models import Document, IngestReport
from src.obs import get_logger, new_run_id
from src.retry import RetryStats

logger = get_logger(__name__)


def ingest_all(
    client: DocumentStoreClient, max_pages: int = 100
) -> tuple[IngestReport, list[Document]]:
    """Fetch every page the store offers. Returns a report and the documents kept."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    run_id = new_run_id()
    started = time.monotonic()
    stats = RetryStats()
    documents: list[Document] = []
    rejected: dict[str, int] = {}
    errors: list[str] = []
    fetched = 0
    total_pages = 1
    index = 0

    logger.info("ingest starting", extra={"source": client.base_url})

    while index < total_pages and index < max_pages:
        try:
            page = client.fetch_page(index, stats=stats)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            message = f"page {index}: {type(exc).__name__}: {str(exc)[:160]}"
            errors.append(message)
            if index == 0:
                # The first request is not just one page. It is where the store
                # tells us how many pages exist. Lose it and we do not know what
                # we are missing, so we stop and say so rather than quietly
                # reporting success over a single page we never read.
                logger.error(
                    "first page lost, cannot tell how much data exists",
                    extra={"page": index, "detail": message},
                )
                break
            logger.error("page lost", extra={"page": index, "detail": message})
            index += 1
            continue

        total_pages = page.total_pages
        fetched += 1
        documents.extend(page.documents)
        for reason, count in page.rejected.items():
            rejected[reason] = rejected.get(reason, 0) + count
        logger.info(
            "page fetched",
            extra={"page": index, "kept": len(page.documents),
                   "dropped": sum(page.rejected.values())},
        )
        index += 1

    report = IngestReport(
        run_id=run_id,
        pages_requested=min(total_pages, max_pages),
        pages_fetched=fetched,
        documents_accepted=len(documents),
        documents_rejected=sum(rejected.values()),
        rejected_reasons=rejected,
        http_attempts=stats.attempts,
        retries=stats.retries,
        slept_seconds=round(stats.slept_seconds, 3),
        duration_seconds=round(time.monotonic() - started, 3),
        errors=errors,
    )
    logger.info(
        "ingest finished",
        extra={"accepted": report.documents_accepted, "rejected": report.documents_rejected,
               "pages_lost": report.pages_requested - report.pages_fetched,
               "retries": report.retries, "complete": report.complete},
    )
    return report, documents
