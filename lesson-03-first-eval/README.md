# Your First Eval Before Your First Feature

*Your answers are wrong 45% of the time. Spending the next three weeks on a better model would fix only a few points of that.*

| | |
|---|---|
| **Series** | AI Forward Deployed Engineer |
| **Arc** | Arc 1 · The Engagement Loop |
| **Lesson** | 3 of 35 — the gate every later lesson has to pass |
| **Audience** | Engineers · Architects · PMs · QA · Data engineers |
| **Read time** | 10 min |
| **Build time** | 2 hours |
| **Prerequisites** | Lesson 1's documents and question set. Python 3.12. |
| **Cost to run** | Zero. A remote Ollama host for `make eval`; the tests need no model at all. |
| **Bar check** | Build a defensible golden set for an unfamiliar domain in 60 minutes |

---

## The problem

Missing evaluation is the most-cited blocker to getting enterprise AI into production, named by more leaders than governance friction or model reliability. That is a strange thing to be top of the list. Evals are not hard to build. This lesson builds one in about two hours.

They get skipped because they feel like overhead before there is anything to measure. So the feature ships first, then the eval never arrives, and the team spends its budget arguing about which model to try next.

Here is what that costs. Meridian's adjusters ask questions, keyword search picks documents, a model reads them and answers. When the answer is wrong, two things could have failed, and without an eval you cannot tell which.

---

## What makes an eval worth building

Plenty of eval suites produce a number nobody acts on. These four are what separate the useful ones.

| Property | What it means |
|---|---|
| **Chosen by hand** | Someone picked the cases, including the awkward ones. A random sample is not a golden set. |
| **About facts** | It checks whether the answer contains the fact the adjuster needed, not whether it reads like a model answer. |
| **Pointed** | It says which part failed, so the number turns into a task instead of a worry. |
| **Able to stop you** | It fails the build. An eval you look at when you remember is a dashboard. |

---

## Questions we already know the answers to

A golden set is just the questions the customer agreed are typical, with the answers they agreed are correct. It is their document, and it happens to live in your repository.

Lesson 1 already produced 40 questions whose right answers we know, so the set is nearly free here. On a real engagement you spend an hour with the adjusters instead, and it is the highest-value hour of the project: it turns "make it better" into a number both sides signed.

```python
class EvalCase(BaseModel):
    case_id: str
    question: str
    kind: str                # "lookup" or "concept"
    answer_doc_id: str       # the document that contains the fact, or NO_DOCUMENT
    expected: str
    match: MatchKind
```

**What to notice:** `expected` is a fact, not a reference answer. The difference decides whether your eval survives contact with reality — more on that below.

**The non-obvious part:** you pick these questions by hand. You do not sample them. The first version of this lesson drew 40 questions at random, and by luck not one landed on a claim whose reserve had never been set. Roughly one claim in seven is like that. The suite therefore could not tell the difference between a system that says "not yet established" and one that invents a plausible number, which is the single worst failure a claims assistant can have. Two cases are now added deliberately:

```python
missing = next((c for c in claims if c.reserve_amount is None), None)
# ... a reserve question for a claim that has no reserve

absent = next(f"C-{n}" for n in range(9000, 9100) if f"C-{n}" not in known)
# ... a question about a claim that does not exist at all
```

**What to notice:** the second case has no answering document anywhere. The only correct response is a refusal, and the scorer treats the refusal itself as the expected fact.

---

## What counts as a right answer

Two scorers, and there are only two because a scorer you cannot explain to a customer is a scorer they will not trust.

```python
def score(case: EvalCase, answer: str) -> bool:
    if not answer.strip():
        return False
    if case.match is MatchKind.NUMERIC:
        return bool(_numbers_in(case.expected) & _numbers_in(answer))
    return _normalise(case.expected) in _normalise(answer)
```

`contains` ignores case and spacing. `numeric` compares numbers whatever the formatting around them, so `12,345.67` and `12345.67` match, and `2,500.00` matches `2500`.

**The non-obvious part:** the tempting alternative is to write a model answer for each question and compare against it. That grades writing style. Reword your prompt to be more concise and your score drops, though nothing about the system got worse. Grading the fact the adjuster needed is stable under every rewording that keeps the fact.

---

## How good could any model be?

This is the piece that makes the eval point at the broken part instead of just reporting a bad number.

An oracle here means a stand-in that is perfect at reading and useless at everything else.

`OracleLLM` is a model that cannot reason, read or guess. It checks whether the expected fact is present in the prompt and repeats it if so, and otherwise refuses.

```python
class OracleLLM:
    def complete(self, prompt: str) -> Completion:
        question = ...                       # parsed out of the prompt
        expected = self._expected.get(question)
        if expected and _loosely_present(expected, prompt):
            return Completion(text=expected, ...)
        return Completion(text="The context does not contain the answer.", ...)
```

**What to notice:** it never reasons or guesses. Its score is therefore the best any model could do, given the documents search handed it.

Run it first:

```
Golden set — oracle (retrieval ceiling)
  model                oracle
  cases                42
  answer in context        59%   <- retrieval, answerable only
  answered correctly       60%   <- the whole system
    with a claim number   100%
    plain language         15%
  lost after retrieval    0.0%   <- the model's share
```

A perfect model scores 60%. Whatever you do next, 40 points are already gone before the model is asked anything.

---

## Run it

Uses a remote Ollama host (no local Docker / local Ollama required).

```bash
# once: confirm the host and install
curl -s http://192.168.1.10:11434/api/tags | python3 -m json.tool | head
make install

# offline gate (no model)
make check

# golden set against the remote model
make eval
# equivalent:
# make eval EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=llama3.1:8b
```

```
Golden set — local model llama3.1:8b
  model                llama3.1:8b
  cases                42
  answer in context        59%   <- retrieval, answerable only
  answered correctly       55%   <- the whole system
    with a claim number    95%
    plain language         10%
  lost after retrieval    4.9%   <- the model's share
  mean seconds/case       1.48
  completion tokens        466
```

`EVAL_OLLAMA_HOST` and `MODEL` are Makefile defaults. Change the host or model
with `make eval EVAL_OLLAMA_HOST=... MODEL=...` — the model name must already
exist on that host (`llama3.2:3b` may not).

If Ubuntu fails with connection refused but Cursor works, your Ubuntu shell
probably has `OLLAMA_HOST=127.0.0.1` exported. That used to override Make; the
recipe now ignores it and uses `EVAL_OLLAMA_HOST` instead. Confirm with
`make -n eval` (it should print `OLLAMA_HOST=http://192.168.1.10:11434 ...`).

---

## What the numbers say

Put the two runs side by side and the argument settles itself.

| | Perfect model | Remote model (`llama3.1:8b`) | Gap |
|---|---|---|---|
| Answer reached the model | 59% | 59% | — |
| Answered correctly | 60% | 55% | 5 points |
| With a claim number | 100% | 95% | 5 points |
| Plain language | 15% | 10% | 5 points |

The system is wrong on 45% of questions. Of that, **about 5 points belong to the model** and **about 40 points belong to search**. Retrieval is still several times the problem the model is.

That changes what you do on Monday. Swapping in a frontier model buys you at most a handful of points and costs you the CISO conversation about sending claim data outside the network. Fixing retrieval is worth far more and stays inside the building. Arc 3 of this course is that work, and this eval is how you will prove it landed.

**The non-obvious part:** the metric that carries this insight nearly did not survive its own tests. Counting the refusal case in the retrieval rate made "lost after retrieval" go *negative*, because that case is answered correctly precisely when nothing is retrieved. Retrieval rate is now computed over answerable cases only. A metric that can go negative is a metric whose definition is wrong, and the test that caught it is four lines long.

---

## Making the build fail when quality drops

A number that never blocks anyone is a number that quietly drifts.

```bash
make gate
```

```
  no regression against evals/baseline.json
```

`evals/baseline.json` holds four metrics from the last accepted run. Any of them falling more than two points fails the build and names which one. Degrade retrieval on purpose and it says so:

```
$ python -m src.main --model oracle --top-k 1 --gate
  REGRESSION
    accuracy: 60% -> 19%  (down 40%)
    accuracy_lookup: 100% -> 36%  (down 64%)
    accuracy_concept: 15% -> 0%  (down 15%)
    retrieval_hit_rate: 59% -> 17%  (down 41%)
```

**What to notice:** the gate runs against the stand-in, not the remote model. That keeps `make check` offline, repeatable and about a second long, and it still catches the changes that matter — a broken search step, damaged documents, a scorer that stopped matching. Model quality is a separate target you run deliberately.

This is also why every test in this lesson uses a stub:

```python
llm = ScriptedLLM(default="The context does not contain the answer.")
report, _ = run_eval(cases, documents, llm, label="refuser")
assert report.accuracy < 0.05
assert report.retrieval_hit_rate > 0.4
```

A suite whose result depends on a model's sampling is a weather report.

---

## What it costs to run

| | |
|---|---|
| `make check` | ~2 seconds, no network, no model |
| `make eval` | 42 cases against `EVAL_OLLAMA_HOST`, ~1.5 s each, about a minute |
| Tokens | ~466 completion tokens for the whole run |
| Money | none |

Remote inference still costs something, just in seconds rather than dollars. The tracker in lesson 4 turns these figures into a cost per claim that transfers to a hosted provider unchanged.

---

## Check it yourself

- [ ] `make check` passes with no services running and no network
- [ ] `make eval` reports both a model accuracy and a retrieval rate
- [ ] The oracle scores well below 100%, and you can say what the gap is made of
- [ ] `python -m src.main --model oracle --top-k 1 --gate` fails and names every metric that dropped

---

## What you just built

- A **curated golden set** of 42 cases, including a claim with no reserve and a claim that does not exist
- **Two fact-based scorers** that survive rewording
- An **oracle** that measures the ceiling retrieval imposes
- A **gate** that fails the build on regression, running offline in about a second
- **56 tests at 96% coverage**, none of which call a model

---

## Five things to remember

1. **The eval's job is attribution.** A single accuracy number tells you that you are unhappy. The split between retrieval and model tells you what to do.
2. **Pick the questions by hand.** Random selection missed the missing-reserve case completely, and that is the one where a wrong answer does real harm.
3. **Check for the fact, not the wording.** Comparing against a model answer measures writing style, and the score moves every time you reword a prompt.
4. **Put the blocking check on the path that never varies.** Stop the build with the stand-in. Measure the real model when you choose to.
5. **A metric that can go negative is defined wrong.** Ours could, for one run, and a four-line test found it.

---

## Where this fits

Lesson 1 measured the customer's current search and found 57% overall. This lesson shows that adding a model on top moves that to about 55%, which is not an improvement, and explains exactly why. Lesson 4 attaches a cost to every operation here. Arc 3 rebuilds retrieval, and lesson 15 reruns this same golden set to prove it worked, against a baseline committed today.

---

## Your FDE interview edge

Anthropic's applied AI loop grades candidates on running a real discovery conversation with a simulated buyer, and case work carries roughly half the weight across comparable loops. The question that separates people is some version of "the accuracy is 55%, what do you do next?"

The weak answer names a bigger model. The strong answer is that you cannot know yet, that you would measure the ceiling retrieval imposes first, and that the number decides whether this is a retrieval project or a model project. That is a ninety-second answer, and this lesson is the evidence behind it.

**Bar check:** given an unfamiliar domain and a subject-matter expert for one hour, produce a golden set someone would sign off on. Sixty minutes.

---

## Next

**Lesson 4 — Cost, latency and unit economics.** You know the system is wrong 45% of the time. The next question in the room is what the 55% costs per claim, and what happens at ten times the volume.
