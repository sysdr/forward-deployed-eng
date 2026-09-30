# Implementation Guide — Lesson 2

Build it from an empty directory. Nothing here needs an account, a key, a
container, or a network connection beyond your own machine.

About two hours. You need lesson 1's `src/models.py` and `src/corpus.py`, which are
already in this lesson's ZIP.

---

## Step 0 — Check your Python

```bash
python3 --version   # 3.12 or newer
```

---

## Step 1 — Set up the project

```bash
mkdir -p lesson-02/{src,tests,diagrams} && cd lesson-02
touch src/__init__.py tests/__init__.py
cp ../lesson-01/src/models.py ../lesson-01/src/corpus.py src/
```

```bash
cat > requirements.txt <<'EOF'
pydantic>=2.9,<3.0
httpx>=0.27
pytest>=8.3
pytest-cov>=5.0
mypy>=1.11
ruff>=0.6
EOF
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

**What to notice:** `httpx` is the only new dependency. There is no server
framework, because the standard library already has one.

---

## Step 2 — Build a store that breaks on purpose (`src/store.py`)

This is the piece people skip, and it is the piece that makes everything else
testable. A real HTTP server, on a real socket, that you can tell to misbehave.

```python
class FaultProfile(BaseModel):
    server_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rate_limit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    malformed_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    invalid_record_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    hang_seconds: float = 3.0
    seed: int = 20260908
```

**What to notice:** `seed`. Faults are drawn from a seeded sequence keyed on the
request number, so the same run fails in the same places and a test can assert on
the outcome. Random faults give you a suite that passes on Tuesday.

Bind to port zero and let the operating system choose:

```python
self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
```

**What to notice:** port zero. Hard-code 8080 and the suite breaks the day someone
runs two tests at once, or has something else listening.

Give it the four faults that actually happen:

```python
if roll < p.server_error_rate:
    self._send(503, b'{"error":"service unavailable"}')
...
if roll < p.timeout_rate:
    time.sleep(p.hang_seconds)      # a real hang, not a raised exception
...
if roll < p.malformed_rate:
    self._send(200, payload[: len(payload) // 2])   # a real truncated body
```

**What to notice:** the hang really sleeps and the truncated body is really cut in
half. A mock that raises `TimeoutError` proves you handle the exception you
imagined. A server that stops responding proves you handle what happens.

---

## Step 3 — Logs you can search at three in the morning (`src/obs.py`)

```python
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
            "run_id": current_run_id(),
            "where": f"{record.module}.{record.funcName}:{record.lineno}",
        }
        for key, value in record.__dict__.items():
            if key not in _BUILTIN and not key.startswith("_"):
                payload.setdefault(key, value)
        return json.dumps(payload, default=str)
```

**What to notice:** `default=str`. Without it, one log line containing something
unusual raises inside your logger, and losing your logs at the exact moment
something went wrong is a bad trade.

The identifier lives in a `ContextVar`, so it follows the run rather than being
passed through every function:

```python
_run_id: ContextVar[str] = ContextVar("run_id", default="")
```

And the line everyone forgets:

```python
logger.propagate = False
```

**What to notice:** without it, every line prints twice as soon as a second module
asks for a logger, and you will lose an hour deciding whether your loop ran twice.

---

## Step 4 — Decide which failures are worth another go (`src/retry.py`)

```python
PERMANENT_STATUS = frozenset({400, 401, 403, 404, 405, 409, 410, 422})

def is_worth_retrying(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code not in PERMANENT_STATUS
    return isinstance(exc, httpx.TransportError)
```

**What to notice:** the last line. Only transport problems get retried, so a
`KeyError` in your own code fails immediately instead of being tried four times.
Catching everything and retrying it is how a five-second bug becomes a
twenty-second bug.

```python
delay = min(base * (factor ** (attempt - 1)), cap)
if jitter:
    delay *= 0.5 + source.random()
```

**What to notice:** the multiplier. Doubling alone means every client that failed
together comes back together. Prove it to yourself:

```python
def test_jitter_spreads_clients_apart(self) -> None:
    flat = {backoff_delay(3, base=1.0, jitter=False) for _ in range(50)}
    spread = {backoff_delay(3, base=1.0, jitter=True, rng=random.Random(i)) for i in range(50)}
    assert len(flat) == 1
    assert len(spread) > 40
```

---

## Step 5 — One door in and out (`src/client.py`)

Everything that can go wrong with someone else's network is handled in this file,
so the rest of the program can be written as though data simply arrives.

```python
try:
    body = response.json()
except json.JSONDecodeError as exc:
    raise httpx.ReadError(f"unreadable body from page {index}: {exc}") from exc
```

**What to notice:** a 200 you cannot parse is turned into a transport error, which
means it gets retried. The usual cause is a connection cut mid-response, and that
often works on the next attempt.

Check every record before it goes any further:

```python
try:
    documents.append(Document.model_validate(record))
except ValidationError as exc:
    field = ".".join(str(p) for p in exc.errors()[0]["loc"]) or "unknown"
    reason = f"{field}: {exc.errors()[0]['type']}"
```

**What to notice:** the rejection names the field. "validation failed" in a log at
3am tells you nothing you can act on. `text: missing` tells you exactly which
upstream export is broken.

---

## Step 6 — Pull every page without ever raising (`src/ingest.py`)

```python
if index == 0:
    logger.error("first page lost, cannot tell how much data exists", ...)
    break
```

**What to notice:** the first request is not just one page. It is where the store
tells you how many pages exist. Lose it and you do not know what you are missing,
so stop loudly rather than report success over a single page you never read. This
is the difference between the two runs in step 7.

The pipeline returns a report on success and on failure alike:

```python
report = IngestReport(
    run_id=run_id, pages_requested=..., pages_fetched=fetched,
    documents_accepted=len(documents), documents_rejected=sum(rejected.values()),
    errors=errors,
)
```

**What to notice:** `run_id` is in the report and in every log line, so a number
someone questions can be traced back to the events that produced it.

---

## Step 7 — Run it, then break it

```bash
make run
```

```
  pages fetched        15 of 15
  documents kept       749
  http requests made   20
  of those, retries    5
  server saw           {'200': 15, '503': 5}
```

Now take the retries away:

```bash
make noretry
```

```
  pages fetched        0 of 1
  documents kept       0
  pages lost           1
      page 0: HTTPStatusError: Server error '503 Service Unavailable'
```

**What to notice:** not 30% worse. Nothing at all. The first request failed, and
the first request is where you learn there are fifteen pages.

```bash
make demo
```

```
  without jitter  40 of 40 clients arrive together
  with jitter     8 of 40 clients arrive together
```

---

## Step 8 — Check that everything passes

```bash
make check
```

```
73 passed
Required test coverage of 90% reached. Total coverage: 94.92%
Success: no issues found in 17 source files
All checks passed!
Lesson 2 green.
```

The suite takes about 25 seconds, which is slower than lesson 1, because these
tests start real servers and wait for real timeouts. That is the trade, and it is
worth it.

---

## Four ways to get this wrong

| Mistake | What happens |
|---|---|
| Mocking the client instead of running a server | You prove you handle the exception you imagined, not the one the network produces |
| Retrying every exception | A wrong credential burns the full retry budget, and a bug in your own code takes four times as long to surface |
| Backoff without jitter | Every client that failed together returns together and knocks the service over as it recovers |
| One log line per run | You get "ingest failed" and no way to find which page, which record, or which of yesterday's forty runs |

---

## Bar check

Twenty minutes. You are handed a failing integration and this log:

```
502 Bad Gateway        x14
403 Forbidden          x220
Read timeout           x31
409 Conflict           x8
```

Say which of those you would retry and which you would not, what backoff you would
use, and what you would change first. You are done when you can defend the 403 and
the 409 decisions to someone who disagrees.
