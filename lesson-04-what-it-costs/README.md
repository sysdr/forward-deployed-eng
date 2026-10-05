# What the Working Half Costs

*The model bill for a 120-person claims department is sixty dollars a month. That is not the number that gets this cancelled.*

| | |
|---|---|
| **Series** | AI Forward Deployed Engineer |
| **Arc** | Arc 1 · The Engagement Loop |
| **Lesson** | 4 of 35 — the number the room asks for next |
| **Audience** | Engineers · Architects · PMs · Engineering managers · Finance |
| **Read time** | 8 min |
| **Build time** | 90 min |
| **Prerequisites** | Lesson 3's golden set and gate. Python 3.12. A remote Ollama host for `make budget` / `make load`. |
| **Cost to run** | Zero, including the part that prices a hosted API. |
| **Bar check** | Price an AI feature and defend it to a CFO-shaped question, 30 minutes |

---

## The problem

Lesson 3 left you with a system that answers 52% of questions correctly and a
clear reason why. The next question in the room is never about accuracy. It is
"what does this cost", and the honest answer decides whether you get to build it.

The leading reported cause of finished AI systems being cancelled is not that they
did not work. It is infrastructure cost landing several times over projection and
destroying the case that got them approved.

That failure has a specific shape, and this lesson measures it.

---

## What a defensible number has

| Property | What it means |
|---|---|
| **Measured** | It comes from a run, not from a rate card and an assumption about volume. |
| **Per unit of their work** | Cost per claim question, not cost per thousand tokens. |
| **Priced for failures too** | The questions that got nothing useful still spent money. |
| **Reproducible** | Anyone can check it with a calculator from the figures you printed. |
| **Sensitive** | It says what would make the number move, before someone finds out. |

---

## Measuring without changing anything

`MeteredClient` wraps any model client and records what it spent. The code doing
the work does not know:

```python
class MeteredClient:
    def __init__(self, inner: LLMClient, stable_prefix: str = "") -> None:
        self.inner = inner
        self.name = inner.name
```

**What to notice:** it keeps the inner name and passes the answer straight
through. Measuring cost should never mean editing the thing being measured, or
you will stop doing it the first week it is inconvenient.

**The non-obvious part:** it also counts the leading section of the prompt that is
identical on every call. Providers that bill cached input cheaply charge a
fraction for that part, which inverts the usual instinct. A system sending a long
stable instruction block and a short variable tail can cost less than one building
a short prompt fresh each time. Of our 17,873 prompt tokens, 2,184 are that stable
block.

---

## Two denominators, and only one is honest

```python
per_question = round(run_cost.total / asked, 6)
per_answered = round(run_cost.total / answered, 6) if answered else 0.0
```

One measured run costs $0.0557 on a hosted API. Divide by the 42 questions asked
and you get $0.001327. Divide by the 22 that were answered correctly and you get
$0.002533.

**The non-obvious part:** the failures are not free. They retrieved documents,
filled a context window and produced tokens, and then produced nothing useful.
Pricing only the successes understates the bill by exactly the amount your system
is wrong, which for us is a factor of nearly two. It is the most common mistake in
this exercise and it always points the same way.

---

## Run it

Uses a remote Ollama host (no local Docker / local Ollama required).

```bash
# once: confirm the host and install
curl -s http://192.168.1.10:11434/api/tags | python3 -m json.tool | head
make install

# offline gate (no model)
make check

# price a real run against the remote model
make budget
# equivalent:
# make budget EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=llama3.2:3b

# latency under concurrency
make load
```

```
Measured on 42 questions with llama3.2:3b
  answered correctly       52%
  calls                     42
  prompt tokens         17,873
  of those, cacheable    2,184
  completion tokens        534
  p50 / p95 seconds       1.15 / 3.52

  a hosted API at illustrative rates
      per question asked     $  0.001327
      per question answered  $  0.002533   <- what they are buying
      120 adjusters, 18 questions a day
      per month              $     60.19
      per month at 10x       $    601.90
```

`EVAL_OLLAMA_HOST` and `MODEL` are Makefile defaults. Change the host or model
with `make budget EVAL_OLLAMA_HOST=... MODEL=...` — the model name must already
exist on that host.

If Ubuntu fails with connection refused but Cursor works, your Ubuntu shell
probably has `OLLAMA_HOST=127.0.0.1` exported. That used to override Make; the
recipe now ignores it and uses `EVAL_OLLAMA_HOST` instead. Confirm with
`make -n budget` (it should print `OLLAMA_HOST=http://192.168.1.10:11434 ...`).

Running the same token usage on a small always-on server instead of a hosted API
prices to under a dollar a month.

---

## What the numbers say

Sixty dollars a month, for a department of 120 adjusters. At ten times the volume,
six hundred.

For an audience braced to hear about GPU bills, that is a surprise, and it is the
right one. **The model is not the expensive part of this system.** An adjuster
costs more per hour than this costs per month.

So the cost conversation should not be about tokens. It should be about the two
numbers underneath, and both are worse than the bill.

**The first is the failure rate.** Cost per answered question is nearly twice cost
per question asked, because 48% of the time you paid for nothing.

**The second is latency.** p95 is 3.52 seconds for one person at a time. Under
load it gets worse:

```
   at once      p50      p95   per minute   errors
         1     2.05     4.08         26.8        0
         2     2.42     2.92         51.9        0
         4     4.39     4.87         55.4        0
```

Throughput stops improving between two and four while the median doubles. One
machine is saturated at two concurrent questions. You do not need more machines
for the volume, which is tiny. You need them to keep the answer quick, which is
a different purchase and a different argument.

**The non-obvious part:** the token figures are stable across runs because the
model samples at temperature zero, but the machine-time and latency figures move
by a fifth between runs on the same laptop. Quote a token cost as a number and a
latency as a range, or you will be asked why the second slide disagrees with the
first.

---

## What actually grows the bill

The base figure is small enough to wave away, which is exactly why teams are
surprised a year later.

```
      scenario                              x    per month
      as measured today                   1.0$       60.19
      an agent that takes 8 steps         8.0$      481.52
      ten times the context               3.5$      210.66
      retries on a flaky quarter          1.2$       75.24
      all three together                 35.0$    2,106.65
```

None of those three is an unreasonable decision. Letting the model plan and
re-check its own work is lesson 16. Retrieving more context is lesson 11. Retrying
transient failures is lesson 2, and you already built it.

They arrive separately, months apart, each justified on its own. Multiplied, they
are the three-to-five times overrun the studies describe, and by then the pilot
was approved on the sixty.

---

## What it costs to run

| | |
|---|---|
| `make check` | about 2 seconds, no model, no network |
| `make budget` | 42 questions against `EVAL_OLLAMA_HOST`, about a minute |
| `make load` | concurrency sweep against the same host, under a minute |
| Money | none, including pricing the hosted option |

---

## Check it yourself

- [ ] `make check` passes with no services and no network
- [ ] `curl http://192.168.1.10:11434/api/tags` lists a model you can pass as `MODEL`
- [ ] `make budget` prints a cost per answered question for local and hosted
- [ ] `make load` shows p50 rising while throughput flattens
- [ ] Multiplying the printed per-question figure by 45,360 gives the printed monthly

---

## What you just built

- A **meter** that records tokens and latency without touching the code it measures
- A **dated price book** in one file, so nothing else in the lesson states a price
- **Two denominators**, and the gap between them priced at nearly 2x
- A **load test** proving one machine saturates at two concurrent questions
- A **sensitivity table** turning $60 into $2,106 through three ordinary decisions
- **49 tests at 93% coverage**, none of which call a model

---

## Five things to remember

1. **Divide by the customer's unit of work.** Cost per claim question is a
   decision. Cost per thousand tokens is trivia.
2. **The failures are not free.** Price the questions that got nothing, or you
   understate by exactly your error rate.
3. **The model is rarely the expensive part.** Latency and wrong answers cost more
   than tokens, and neither is on the invoice.
4. **Round once and print what you computed with.** A figure a CFO cannot
   reproduce is a meeting about arithmetic.
5. **Quote the multipliers with the number.** Nobody decides to spend 35 times
   more. They make three sensible decisions.

---

## Where this fits

Lesson 3 said retrieval costs 41 points of accuracy and the model costs 7. This
lesson prices both halves and finds the money is not where anyone expects. Arc 3
rebuilds retrieval, and now you can argue it on latency and cost as well as
accuracy. Lesson 16 builds the agent whose eight steps are the biggest multiplier
in the table above, and you will meet this number again there.

---

## Your FDE interview edge

"How much will this cost?" is a question candidates answer with a rate card. The
answer that lands has three parts: here is what a measured run cost, here is the
cost per unit of your work with failures included, and here are the three things
that would multiply it.

The last part is what separates someone who has shipped from someone who has
prototyped. Anyone can price the happy path.

**Bar check:** price this for a 400-adjuster department and defend it against
"what happens when everyone turns it on at once". Thirty minutes.

---

## Next

**Lesson 5 — Shipping with coding agents in someone else's repository.** You can
measure what the system costs. The next constraint is how fast you can build it
inside a customer's codebase without exceeding what they authorised.
