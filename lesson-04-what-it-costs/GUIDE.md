# Implementation Guide — Lesson 4

Build it from lesson 3's system. About ninety minutes. Nothing here costs money,
including the part that prices a hosted API.

You need lesson 3's `src/` and `evals/baseline.json`, which are already in this
lesson's ZIP.

---

## Step 0 — Point at the model, once

This lesson talks to a remote Ollama host. You do not need Docker or a local
model for `make budget` and `make load`.

```bash
# confirm the remote host is up and see which models it has
curl -s http://192.168.1.10:11434/api/tags | python3 -m json.tool | head

# install this lesson
make install
```

Defaults in the `Makefile`:

| Variable | Default | Purpose |
|---|---|---|
| `EVAL_OLLAMA_HOST` | `http://192.168.1.10:11434` | where `make budget` and `make load` send requests |
| `MODEL` | `llama3.2:3b` | must be a model name that host already has |

Override either when you run, for example
`make budget EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=qwen3:4b`.

Do not rely on a shell `export OLLAMA_HOST=...` for this lesson. That variable
is reserved by the Ollama CLI and, if set to `127.0.0.1`, used to make `make`
point at localhost instead of the remote host. `make budget` and `make load`
set `OLLAMA_HOST` from `EVAL_OLLAMA_HOST` for the Python process only.

**What to notice:** you only need the remote host for `make budget` and
`make load`. Every test and the gate itself run without it (`make check`).

---

## Step 1 — Put the prices in one dated file (`src/pricing.py`)

```python
PRICES_CHECKED = "2026-09-08"
"""Update this date whenever you touch the numbers below."""
```

**What to notice:** the date. Prices are the only thing in this lesson that goes
stale, so they live in one file that says how old it is. Nothing anywhere else in
the lesson states a price.

Two ways of paying, and you need both:

```python
class TokenPrice(BaseModel):     # hosted: pay per token, nothing when idle
class MachinePrice(BaseModel):   # local: pay by the hour, busy or not
```

**What to notice:** `MachinePrice` for the laptop is set to zero. That is not the
same as free. It is the cheapest option, with a number on it, which is what lets
you compare it against a hosted API instead of waving your hands.

---

## Step 2 — Count what every call spends (`src/meter.py`)

Wrap the client rather than editing it:

```python
class MeteredClient:
    def __init__(self, inner: LLMClient, stable_prefix: str = "") -> None:
        self.inner = inner
        self.name = inner.name
```

**What to notice:** it keeps the inner client's name and returns its answer
unchanged, so nothing downstream knows it is being measured. Measuring cost should
never mean changing the code that does the work, or you will stop measuring the
first time it is inconvenient.

```python
if self.stable_prefix and prompt.startswith(self.stable_prefix):
    cached = len(self.stable_prefix) // 4
```

**What to notice:** four characters per token is a rough conversion, and the
comment in the file says so. It is close enough to compare two designs and not
close enough to put on an invoice. Say which of those you are doing.

---

## Step 3 — Pick the denominator (`src/budget.py`)

This is the whole lesson in six lines:

```python
per_question = round(run_cost.total / asked, 6)
per_answered = round(run_cost.total / answered, 6) if answered else 0.0
```

**What to notice:** two divisions, from one cost. The questions that failed still
consumed tokens. Pricing only the ones that worked is how an estimate comes in
several times under, and it is the most common mistake in this whole exercise.

Now the part that only matters in a meeting:

```python
# Round once, here, and derive everything else from the rounded figure.
per_question = round(run_cost.total / asked, 6)
```

**What to notice:** the monthly figure is computed from the rounded per-question
figure, not from full precision. The first version of this lesson did the
opposite, and the printed numbers disagreed with each other by two pence. A number
a CFO cannot reproduce with a calculator is a number you will spend the meeting
defending instead of the proposal. There is a test for it.

---

## Step 4 — Show what makes the bill grow

```python
rows = [
    ("as measured today", 1.0, "one retrieval, one model call, short answers"),
    ("an agent that takes 8 steps", 8.0, "the same question, planned and re-checked"),
    ("ten times the context", 3.5, "more documents retrieved per question"),
    ("retries on a flaky quarter", 1.25, "lesson 2's retry policy in a bad month"),
    ("all three together", 8.0 * 3.5 * 1.25, "none of these is unreasonable alone"),
]
```

**What to notice:** none of these is exotic. Each is an ordinary decision taken
months after the pilot was approved. The base number is small enough to ignore,
which is exactly why teams are surprised later.

---

## Step 5 — Measure it under load (`src/loadtest.py`)

```python
gate = threading.Semaphore(concurrency)
```

**What to notice:** the semaphore, and the test that proves it works:

```python
def test_concurrency_is_actually_limited(self) -> None:
    ...
    run_load(work, requests=12, concurrency=3)
    assert peak <= 3
```

If that limit were broken the whole load test would be a lie, and it would look
fine.

Errors are counted, not raised:

```python
except Exception:  # noqa: BLE001 - counted, and the run continues
    errors += 1
```

**What to notice:** a load test that stops at the first failure measures the time
until your first failure, which is not what you wanted to know.

---

## Step 6 — Run it

```bash
make budget
# equivalent:
# make budget EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=llama3.2:3b
```

```
  calls                     42
  prompt tokens         17,873
  of those, cacheable    2,184
  completion tokens        534
  p50 / p95 seconds       1.23 / 4.61
```

```bash
make load
# equivalent:
# make load EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=llama3.2:3b
```

```
   at once      p50      p95   per minute   errors
         1     2.05     4.08         26.8        0
         2     2.42     2.92         51.9        0
         4     4.39     4.87         55.4        0
```

Confirm the recipes point at the remote host with `make -n budget` (it should
print `OLLAMA_HOST=http://192.168.1.10:11434 ...`). If Ubuntu fails with
connection refused but Cursor works, your Ubuntu shell probably has
`OLLAMA_HOST=127.0.0.1` exported — the Make recipes ignore that and use
`EVAL_OLLAMA_HOST` instead.

**What to notice:** throughput stops improving between two and four while latency
doubles. One machine is saturated at two concurrent questions. You do not need
more machines to handle the volume. You need them to keep the answer quick.

---

## Step 7 — Check that everything passes

```bash
make check
```

```
49 passed
Required test coverage of 90% reached. Total coverage: 93%
Success: no issues found in 21 source files
All checks passed!
Lesson 4 green.
```

The gate prices the run with the stub, so it is offline and instant and still
catches broken arithmetic.

---

## Four ways to get this wrong

| Mistake | What happens |
|---|---|
| Dividing only by questions asked | The failures are free in your model and expensive in reality |
| Pricing per thousand tokens | Nobody in the room can convert that into a decision |
| Printing fewer decimals than you computed with | Your slide and their calculator disagree, and you lose the meeting |
| Quoting the pilot number without the multipliers | The bill arrives 35 times larger and the project is cancelled |

---

## Bar check

Thirty minutes. Price the Meridian answerer for a 400-adjuster department and
defend it against these three questions:

1. What happens when we turn it on for everyone at once?
2. What is this number if the model gets more expensive?
3. Why is your cost per answer twice your cost per question?

You are done when every figure you quote can be reproduced from the printed
per-question cost with a calculator.
