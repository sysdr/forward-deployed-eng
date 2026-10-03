# Implementation Guide — Lesson 3

Build the eval from lesson 1's output. Every step is complete, and nothing needs
an account or a key. About two hours.

The one thing you need from lesson 1 is its documents and question set. Copy
`src/corpus.py`, `src/search.py` and `src/models.py` across before you start, or
work in the ZIP for this lesson, which already contains them.

---

## Step 0 — Point at the model, once

This lesson talks to a remote Ollama host. You do not need Docker or a local
model for the eval.

```bash
# confirm the remote host is up and see which models it has
curl -s http://192.168.1.10:11434/api/tags | python3 -m json.tool | head

# install this lesson
make install
```

Defaults in the `Makefile`:

| Variable | Default | Purpose |
|---|---|---|
| `EVAL_OLLAMA_HOST` | `http://192.168.1.10:11434` | where `make eval` sends requests |
| `MODEL` | `llama3.1:8b` | must be a model name that host already has |

Override either when you run, for example
`make eval EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=qwen3:4b`.

Do not rely on a shell `export OLLAMA_HOST=...` for this lesson. That variable
is reserved by the Ollama CLI and, if set to `127.0.0.1`, used to make `make`
point at localhost instead of the remote host. `make eval` sets `OLLAMA_HOST`
from `EVAL_OLLAMA_HOST` for the Python process only.

**What to notice:** you only need the remote host for `make eval`. Every test and
the gate itself run without it (`make check`), which is the point of the next
two hours.

---

## Step 1 — Describe the shapes your data has to fit (`src/models.py`)

Append to lesson 1's models. The one that matters:

```python
class EvalCase(BaseModel):
    case_id: str
    question: str
    kind: str
    answer_doc_id: str       # the document that contains the fact, or NO_DOCUMENT
    expected: str
    match: MatchKind

    @computed_field
    @property
    def answerable(self) -> bool:
        return self.answer_doc_id != NO_DOCUMENT
```

**What to notice:** `answerable`. Some cases have no answering document, because
the correct response is a refusal. Retrieval cannot succeed on those, so they are
excluded from the retrieval rate. Miss this and your metrics punish the system for
behaving correctly, which is covered in step 6.

---

## Step 2 — Write the questions and their right answers (`src/goldenset.py`)

Turn lesson 1's questions into cases with an expected fact:

```python
if q.kind == "concept":
    expected, match = claim.claim_id, MatchKind.CONTAINS
elif q.text.startswith("What is the reserve"):
    if claim.reserve_amount is None:
        expected, match = "not yet established", MatchKind.CONTAINS
    else:
        expected, match = f"{claim.reserve_amount:,.2f}", MatchKind.NUMERIC
```

**What to notice:** `expected` is the fact, not a sentence. You are going to check
whether it appears in the answer, so it has to be the smallest thing that makes
the answer right.

Now the part that is easy to skip:

```python
def _edge_cases(claims, doc_text) -> list[EvalCase]:
    missing = next((c for c in claims if c.reserve_amount is None), None)
    # ... a reserve question for a claim whose reserve was never set

    known = {c.claim_id for c in claims}
    absent = next(f"C-{n}" for n in range(9000, 9100) if f"C-{n}" not in known)
    # ... a question about a claim that does not exist
```

**What to notice:** these two cases are added by hand. The first draft of this
lesson sampled 40 questions and, by chance, not one hit a claim with no reserve,
even though about one claim in seven is like that. The suite could not distinguish
a system that says "not established" from one that invents a number. Write the
test that would have caught it:

```python
def test_the_unset_reserve_case_is_present(self, cases) -> None:
    assert [c for c in cases if c.expected == "not yet established"]
```

---

## Step 3 — Decide what counts as correct (`src/scoring.py`)

```python
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

def _numbers_in(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace(",", "")
        if cleaned.endswith(".00"):
            cleaned = cleaned[:-3]
        found.add(cleaned.rstrip("."))
    return found
```

**What to notice:** stripping `.00`. Without it, an expected `2,500.00` never
matches an answer that says `2500`, and you spend an afternoon convinced the model
is worse than it is.

Score the refusals honestly:

```python
def test_a_refusal_scores_correct_on_an_unanswerable_case(self) -> None:
    c = case("not yet established", MatchKind.CONTAINS)
    assert score(c, "Reserve not yet established pending inspection.")
```

---

## Step 4 — Give the model something to read (`src/answerer.py`)

```python
PROMPT = """You are helping a claims adjuster at an insurance company.
Answer using only the context below. If the answer is not in the context, say
"The context does not contain the answer." Answer in one short sentence.

Context:
{context}

Question: {question}
Answer:"""
```

**What to notice:** the refusal sentence is given verbatim. If you ask a model to
"say you don't know", it will phrase that twenty different ways and your scorer
will miss most of them. Dictating the exact string makes refusals measurable.

---

## Step 5 — Three ways to answer a question (`src/llm.py`)

`OllamaClient` is the only one that touches the network.

```python
"options": {"temperature": 0.0, "num_predict": self.num_predict},
```

**What to notice:** temperature zero. Leave it higher and the model words things
differently each run, so two runs of the same eval disagree and you cannot tell a
real drop from ordinary variation.

`ScriptedLLM` returns fixed replies and is what every test uses. `OracleLLM` is the
interesting one. It is a stand-in that answers perfectly whenever the answer is in
front of it:

```python
expected = self._expected.get(question)
if expected and _loosely_present(expected, prompt):
    return Completion(text=expected, ...)
return Completion(text="The context does not contain the answer.", ...)
```

**What to notice:** it never reasons. It answers when the fact is in front of it
and refuses otherwise, so its score is the ceiling retrieval imposes on every real
model. This is the number that tells you whether to work on retrieval or on the
model.

---

## Step 6 — Ask every question and count the hits (`src/evaluate.py`)

```python
answerable = [r for r in results if r.answerable]

report = EvalReport(
    retrieval_hit_rate=rate(answerable, "retrieved"),   # answerable only
    accuracy=rate(results),                             # every case
    accuracy_answerable=rate(answerable),
    ...
)
```

**What to notice:** three different denominators, on purpose. The first version
computed the retrieval rate over every case, including the refusal case, which is
answered correctly precisely when nothing is retrieved. That pushed accuracy above
the retrieval rate and made "lost after retrieval" negative. The test that caught
it:

```python
def test_oracle_accuracy_equals_its_retrieval_rate(self, cases, documents, oracle):
    report, _ = run_eval(cases, documents, oracle, label="oracle")
    assert report.accuracy_answerable == report.retrieval_hit_rate
    assert report.headroom == 0.0
```

A metric that can go negative is defined wrong. This invariant says so in four
lines.

---

## Step 7 — Make a drop in quality fail the build

```python
GATED_METRICS = ("accuracy", "accuracy_lookup", "accuracy_concept", "retrieval_hit_rate")
TOLERANCE = 0.02

for metric in GATED_METRICS:
    before, after = float(baseline[metric]), float(getattr(report, metric))
    if before - after > tolerance:
        regressions.append(Regression(...))
```

**What to notice:** the tolerance is one number and it is a judgement call. Too
tight and ordinary variation blocks merges until people disable the gate. Too
loose and a real regression walks through. Two points is a starting position you
should revisit once you have a month of runs.

Save the first baseline and commit it:

```bash
make baseline
git add evals/baseline.json
```

---

## Step 8 — Check that everything passes

```bash
make check
```

```
57 passed
Required test coverage of 90% reached. Total coverage: 96%
Success: no issues found in 18 source files
All checks passed!
  no regression against evals/baseline.json
Lesson 3 green.
```

Then prove the gate actually blocks something:

```bash
python -m src.main --model oracle --top-k 1 --gate
```

```
  REGRESSION
    accuracy: 60% -> 19%  (down 40%)
    accuracy_lookup: 100% -> 36%  (down 64%)
    accuracy_concept: 15% -> 0%  (down 15%)
    retrieval_hit_rate: 59% -> 17%  (down 41%)
```

**What to notice:** exit code 1. A gate that prints a warning and passes is a
dashboard with extra steps.

---

## Step 9 — See how the real model does
xczfff mbnbb 
```bash
make check                         # offline: tests, lint, oracle gate
make eval                          # remote model at EVAL_OLLAMA_HOST
# or, explicitly:
make eval EVAL_OLLAMA_HOST=http://192.168.1.10:11434 MODEL=llama3.1:8b
```

Compare it with `make gate`'s oracle numbers. The difference between the two is
the model's contribution. Everything below the oracle's score is retrieval's.

If `make eval` fails with connection refused, check you are not exporting
`OLLAMA_HOST=127.0.0.1` in that shell, and that `EVAL_OLLAMA_HOST` reaches the
remote machine (`curl "$EVAL_OLLAMA_HOST/api/tags"`). If it fails with a
model-not-found error, pick a name from
`curl http://192.168.1.10:11434/api/tags` and pass `MODEL=...`.

---

## Four ways to get this wrong

| Mistake | What happens |
|---|---|
| Sampling the golden set instead of curating it | The cases where a wrong answer does real harm are the rare ones, so sampling is least likely to include them |
| Scoring against a reference answer | You grade prose. Rewording a prompt changes the score without changing the system |
| Counting refusal cases in the retrieval rate | Metrics punish correct behaviour, and derived numbers go negative |
| Letting tests call the model | The suite fails on a slow laptop, passes on a fast one, and nobody trusts it |
| Sampling at temperature above zero | Reruns disagree with each other and you cannot see a real regression |
| A gate that warns instead of failing | It is ignored within two weeks |

---

## Bar check

Sixty minutes. Pick a domain you do not know: a hospital's discharge summaries,
a bank's loan files, a council's planning applications. You have one imaginary
subject-matter expert and one hour.

Produce a golden set someone would sign off on. You are done when it contains at
least three cases where the correct answer is "I don't know", and you can say
which real failure each one guards against.
