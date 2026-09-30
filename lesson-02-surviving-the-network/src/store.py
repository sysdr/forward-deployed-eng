"""A document store that breaks on purpose.

Meridian's real store is a decade-old service behind a corporate proxy. You will
not get access to it in week one, and when you do, you will not be allowed to make
it fail on demand. So this is a stand-in that fails the same ways, runs on your
own machine, and can be told exactly how badly to behave.

It matters that this is a real HTTP server on a real socket. A mocked client
proves your code handles the exception you imagined. A server that actually
returns 503, actually hangs past your timeout, and actually sends truncated JSON
proves it handles what happens.

Faults are chosen from a seeded sequence, so the same run produces the same
failures and a test can assert on the outcome.
"""
from __future__ import annotations

import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field

from src.models import Document


class FaultProfile(BaseModel):
    """How badly the store misbehaves. All rates are per request."""

    server_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rate_limit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    malformed_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    invalid_record_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    hang_seconds: float = 3.0
    seed: int = 20260908


class StoreStats(BaseModel):
    requests: int = 0
    peak_concurrency: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class DocumentStore:
    """A threaded HTTP server serving documents in pages.

    Use it as a context manager:

        with DocumentStore(documents, FaultProfile(server_error_rate=0.3)) as store:
            ...  # store.url is live
    """

    def __init__(
        self,
        documents: list[Document],
        profile: FaultProfile | None = None,
        page_size: int = 50,
        token: str | None = None,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be at least 1")
        self.documents = documents
        self.profile = profile or FaultProfile()
        self.page_size = page_size
        self.token = token
        self.stats = StoreStats()

        self._lock = threading.Lock()
        self._active = 0
        self._seq = 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        address = self._server.server_address
        host = address[0].decode() if isinstance(address[0], bytes) else str(address[0])
        return f"http://{host}:{int(address[1])}"

    @property
    def pages(self) -> int:
        return max(1, -(-len(self.documents) // self.page_size))

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> DocumentStore:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _record_status(self, status: int) -> None:
        with self._lock:
            key = str(status)
            self.stats.by_status[key] = self.stats.by_status.get(key, 0) + 1

    def _enter_request(self) -> int:
        with self._lock:
            self._seq += 1
            self._active += 1
            self.stats.requests += 1
            self.stats.peak_concurrency = max(self.stats.peak_concurrency, self._active)
            return self._seq

    def _leave_request(self) -> None:
        with self._lock:
            self._active -= 1

    def _page(self, index: int, corrupt: bool) -> dict[str, object]:
        start = index * self.page_size
        chunk = self.documents[start : start + self.page_size]
        records: list[dict[str, object]] = []
        for position, doc in enumerate(chunk):
            record: dict[str, object] = {
                "doc_id": doc.doc_id,
                "claim_id": doc.claim_id,
                "kind": str(doc.kind),
                "text": doc.text,
            }
            # One record per page loses a required field. Real exports do this
            # when an upstream system had a null the exporter did not expect.
            if corrupt and position == 0:
                record.pop("text")
            records.append(record)
        return {"page": index, "pages": self.pages, "documents": records}

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        store = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: object) -> None:
                """Silence the default stderr logging."""

            def _send(
                self, status: int, body: bytes, content_type: str = "application/json"
            ) -> None:
                store._record_status(status)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                if status == 429:
                    self.send_header("Retry-After", "1")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802  (name fixed by the stdlib)
                seq = store._enter_request()
                try:
                    parsed = urlparse(self.path)
                    if parsed.path != "/documents":
                        self._send(404, b'{"error":"not found"}')
                        return

                    if store.token is not None:
                        supplied = self.headers.get("Authorization", "")
                        if supplied != f"Bearer {store.token}":
                            # A permanent failure. Retrying changes nothing.
                            self._send(403, b'{"error":"forbidden"}')
                            return

                    rng = random.Random(store.profile.seed + seq)
                    roll = rng.random()
                    p = store.profile

                    if roll < p.server_error_rate:
                        self._send(503, b'{"error":"service unavailable"}')
                        return
                    roll -= p.server_error_rate

                    if roll < p.rate_limit_rate:
                        self._send(429, b'{"error":"slow down"}')
                        return
                    roll -= p.rate_limit_rate

                    if roll < p.timeout_rate:
                        time.sleep(p.hang_seconds)
                        self._send(504, b'{"error":"gateway timeout"}')
                        return
                    roll -= p.timeout_rate

                    query = parse_qs(parsed.query)
                    try:
                        index = int(query.get("page", ["0"])[0])
                    except ValueError:
                        self._send(400, b'{"error":"page must be an integer"}')
                        return
                    if index < 0 or index >= store.pages:
                        self._send(404, b'{"error":"no such page"}')
                        return

                    corrupt = rng.random() < p.invalid_record_rate
                    payload = json.dumps(store._page(index, corrupt)).encode()

                    if roll < p.malformed_rate:
                        # Truncated response. Valid HTTP 200, unparseable body.
                        self._send(200, payload[: len(payload) // 2])
                        return

                    self._send(200, payload)
                finally:
                    store._leave_request()

        return Handler
