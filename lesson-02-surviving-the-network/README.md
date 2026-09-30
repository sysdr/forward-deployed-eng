# Code That Survives Someone Else's Network

*Turn off retries and this pipeline does not get 30% less data. It gets none.*

| | |
|---|---|
| **Series** | AI Forward Deployed Engineer |
| **Arc** | Arc 1 · The Engagement Loop |
| **Lesson** | 2 of 35 — the habits every later lesson assumes |
| **Audience** | Engineers · Architects · SRE · QA · Data engineers |
| **Read time** | 8 min |
| **Build time** | 2 hours |
| **Prerequisites** | Lesson 1's documents. Python 3.12. |
| **Cost to run** | Zero. The document store runs on your own machine. |
| **Bar check** | Given a failing integration, say what to retry and defend it, 20 minutes |

---

## The problem

Lesson 1's code read its documents from a function call. Meridian's real documents
live in a decade-old service behind a corporate proxy, and the difference is not a
detail.

That service returns 503 when it is busy, 429 when you are quick, nothing at all
when a firewall drops your connection, and half a JSON body when something cuts the
response mid-flight. Every so often it hands you a record with a field missing,
because an upstream system had a null its exporter did not expect.

None of that happens on your laptop, which is why it all happens in week three.

↑ **Diagram 1** shows the shape of the answer: everything they can do to you
arrives through one door.

---

## The four habits

Name them, because you will look for all four in every code review you ever do on
an integration.

| Habit | What it means |
|---|---|
| **Try again, but only sometimes** | Wait and retry the failures that could pass next time. Give up instantly on the ones that cannot. |
| **Check at the edge** | Every record is validated the moment it arrives, and a bad one is counted rather than fatal. |
| **One identifier per run** | Every log line from one run carries the same tag, so you can pull that run out of a file holding fifty others. |
| **Hand back a report** | The pipeline never raises. Failures come back as data the caller can act on. |

---

## A store that breaks on purpose

You will not get access to Meridian's real store in week one, and when you do, you
will not be allowed to make it fail on demand. So build a stand-in that fails the
same ways.

```python
class FaultProfile(BaseModel):
    server_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rate_limit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    malformed_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    invalid_record_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    seed: int = 20260908
```

**What to notice:** `seed`. Faults come from a seeded sequence, so the same run
fails in the same places and a test can assert on the result.

**The non-obvious part:** this is a real HTTP server on a real socket, and that is
the whole point. A mocked client proves you handle the exception you imagined. A
server that actually hangs past your timeout and actually sends half a body proves
you handle what happens. Every test in this lesson goes over a socket, and none of
them uses a mock.

---

## Which failures are worth another go

```python
PERMANENT_STATUS = frozenset({400, 401, 403, 404, 405, 409, 410, 422})

def is_worth_retrying(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code not in PERMANENT_STATUS
    return isinstance(exc, httpx.TransportError)
```

| What came back | Try again? | Why |
|---|---|---|
| 503, 502, 504 | yes | the service is struggling and usually recovers |
| 429 | yes | you were quick; wait and you are welcome back |
| a timeout or dropped connection | yes | the request never got an answer |
| 200 with a body that will not parse | yes | usually a connection cut mid-response |
| 403, 401 | no | the credential is wrong and will be wrong next time |
| 404, 409, 422 | no | the request itself is wrong |

**What to notice:** the last line of the function. Only transport problems retry,
so a `KeyError` in your own code fails immediately instead of four times.

**The non-obvious part:** retrying a 403 is not merely useless. It is four times as
slow to tell you what is wrong, and it spends four times your rate limit doing it.
On an engagement where the customer's security team is already nervous, a burst of
repeated forbidden requests is also the thing that gets your credential suspended.

---

## Waiting in a way that does not make it worse

```python
delay = min(base * (factor ** (attempt - 1)), cap)
if jitter:
    delay *= 0.5 + source.random()
```

Doubling the wait is the obvious half. The random multiplier is the half that
matters, and you can measure it:

```bash
make demo
```

```
Every client fails at once, then retries. Peak load on the way back:
  without jitter  40 of 40 clients arrive together
  with jitter     8 of 40 clients arrive together
```

↑ **Diagram 2** is that measurement drawn out.

**The non-obvious part:** every client that failed at the same moment waits the
same time, so they return in one block. The service that was recovering gets the
whole crowd at once and falls over again, and now you have caused the second
outage. One random multiplier turns a spike into a trickle.

---

## Run it

```bash
make install
make run
```

```
Store failing about 30% of requests, 4 attempts per page

  run id               84596229-da8f-42ad-974f-8e6ef5a4e744
  pages fetched        15 of 15
  documents kept       749
  documents dropped    1
      text: missing                1
  http requests made   20
  of those, retries    5
  time spent waiting   0.99s
  wall clock           1.63s
  server saw           {'200': 15, '503': 5}
  complete             False
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

---

## What the numbers say

Retrying turned 20 requests into all 15 pages and 749 of 750 documents, at a cost
of one second spent waiting. The waiting figure moves a little between runs,
because the jitter is doing its job.

Turning retries off did not cost 30% of the data. It cost all of it, and the reason
is worth more than the retry logic itself: **page zero is where the store tells you
how many pages exist.** Lose it and you do not know what you are missing. The code
now says so out loud rather than quietly reporting success over one page it never
read.

The single dropped document is the other habit earning its place. One record
arrived without its `text` field, and the run rejected that record, named the field
in the log, and kept the other 749. A pipeline that raised there would have thrown
away fourteen good pages over one bad row.

**The non-obvious part:** `complete` is `False` on a run that kept 749 of 750
documents. That is deliberate. "Mostly worked" is a state you want to see in a
report rather than discover in a meeting, and a boolean that only goes false on a
total failure is a boolean nobody checks.

---

## What it costs to run

| | |
|---|---|
| `make check` | about 25 seconds, no network beyond localhost |
| `make run` | 1.6 seconds, 20 HTTP requests |
| Money | none |

The suite is slower than lesson 1's because these tests start real servers and wait
for real timeouts. That is the trade for testing what actually happens.

---

## Check it yourself

- [ ] `make check` passes with no containers and no internet
- [ ] `make run` fetches all 15 pages while the server reports 503s
- [ ] `make noretry` loses everything, and the log line says why
- [ ] `make demo` prints two peak numbers, and the second is much smaller

---

## What you just built

- A **document store that fails on demand**, repeatably, over real HTTP
- A **retry policy** that knows the difference between a 503 and a 403
- **Backoff with jitter**, measured at 40 simultaneous arrivals against 8
- A **validating boundary** that drops one bad record and names the field
- **Structured logs** where every line of a run shares one identifier
- **73 tests at 95% coverage**, not one of them using a mock

---

## Five things to remember

1. **Test against a server, not a mock.** A mock proves you handle the exception
   you imagined.
2. **The first request is special.** It is where you learn the size of the job, so
   losing it is not a partial failure.
3. **Retrying a 403 costs you four times.** Four times the wait, four times the
   quota, and the same answer.
4. **Jitter is not a detail.** Without it, everyone who failed together returns
   together and takes the service down a second time.
5. **Name the field in the rejection.** "Validation failed" at 3am tells you
   nothing you can act on.

---

## Where this fits

Lesson 1 measured the customer's search with everything in memory. This lesson
makes the same documents arrive over HTTP from a service that misbehaves, which is
what they will actually do. Lesson 3 puts an eval and a gate around the result.
Lesson 24 is where the security team asks how this connects to their network, and
the answers are easier when there is exactly one place to point at.

---

## Your FDE interview edge

An interviewer describes a flaky integration and asks what you would do. The weak
answer is "add retries". The strong answer separates the failures that can pass
next time from the ones that cannot, gives a number for the backoff, mentions
jitter and says what it is for, and finishes on the part most people miss: what you
log so that the next failure takes ten minutes to diagnose instead of a day.

**Bar check:** given a log showing 502s, 403s, timeouts and 409s, say which you
would retry and defend the 403 and 409 decisions. Twenty minutes.

---

## Next

**Lesson 3 — Your first eval before your first feature.** The documents arrive
reliably now. The next question is whether the answers built on them are any good,
and how you would know.
