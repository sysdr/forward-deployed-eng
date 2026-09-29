# Implementation Guide — Lesson 1

Build the lesson from an empty directory. Every step is complete; nothing is left
as an exercise, and no step needs an account, a key, or a network connection.

Total time: about 90 minutes. Python 3.12 or newer is the only prerequisite.

---

## Step 0 — Verify your Python

```bash
python3 --version   # need 3.12 or newer
```

The code uses `StrEnum` and the `X | None` type syntax, both of which need 3.12.
If you are on an older Python, install a newer one before continuing rather than
working around it. Every later lesson assumes the same floor.

---

## Step 1 — Scaffold

```bash
mkdir -p lesson-01/{src,tests,diagrams} && cd lesson-01
touch src/__init__.py tests/__init__.py
```

```bash
cat > requirements.txt <<'EOF'
pydantic>=2.9,<3.0
pytest>=8.3
pytest-cov>=5.0
mypy>=1.11
ruff>=0.6
EOF

python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

**What to notice:** five dependencies, all free, all offline after install. If a
lesson in this course ever needs a paid service to run its tests, that is a bug
in the lesson.

---

## Step 2 — Describe the shapes your data has to fit (`src/models.py`)

Start with the models, because they are the argument you are going to have with
the customer, written down.

Copy `src/models.py` from the source tree. The pieces that matter:

```python
class Question(BaseModel):
    question_id: str
    text: str
    answer_doc_id: str
    kind: str  # "lookup" (an identifier) or "concept" (a description)
```

**What to notice:** `answer_doc_id` is a single document, not a list. That is a
commitment: the documents must give exactly one correct answer per question. If
you let it be a list "to be safe," accuracy stops meaning anything and you will
not notice for three lessons.

```python
class BaselineReport(BaseModel):
    accuracy_at_5: float
    accuracy_lookup: float
    accuracy_concept: float
    p50_seconds: float
    ...
    @computed_field
    @property
    def p50_minutes(self) -> float:
        return round(self.p50_seconds / 60, 2)
```

**What to notice:** minutes are computed from seconds, never stored alongside
them. Two fields that can disagree eventually will, and a report that contradicts
itself in front of a customer is worse than no report.

---

## Step 3 — Generate the documents (`src/corpus.py`)

The generator has one job that is easy to get wrong: every concept question must
have exactly one correct answer.

```python
def _loss(i: int) -> dict[str, str]:
    action_doc, action_q, peril = ACTIONS[i % len(ACTIONS)]
    loc_doc, loc_q = LOCATIONS[(i // len(ACTIONS)) % len(LOCATIONS)]
    obj_doc, obj_q = OBJECTS[(i // (len(ACTIONS) * len(LOCATIONS))) % len(OBJECTS)]
    return {
        "peril": peril,
        "doc": f"{action_doc} {loc_doc}, damaging {obj_doc}",
        "query": f"{action_q} {loc_q}, harming {obj_q}",
    }
```

**What to notice:** the integer division strides. Claim 0 and claim 8 share an
action but differ in location, so their descriptions differ. With 8 × 6 × 6 = 288
combinations and 200 claims, no two claims collide. Write the uniqueness test
before you trust this:

```python
def test_loss_descriptions_are_unique_across_the_corpus(self) -> None:
    losses = [_loss(i)["doc"] for i in range(200)]
    assert len(set(losses)) == len(losses)
```

The first draft of this lesson used a flat list of eight scenarios cycled with
`i % 8`. Twenty-five claims shared each description, every concept question had
twenty-five correct answers, and the accuracy number was meaningless. The test
above is what caught it.

Then add the mess deliberately, and test for it, so a future tidy-up cannot
silently make the baseline easier:

```python
def test_three_date_formats_appear(self) -> None: ...
def test_some_claims_have_no_reserve(self) -> None: ...
def test_adjuster_names_are_spelled_inconsistently(self) -> None: ...
```

---

## Step 4 — Build the search they use today (`src/search.py`)

```python
_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]*")

def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]
```

**What to notice:** the hyphen is inside the character class. Drop it and `c-1042`
becomes `c` and `1042`, every claim identifier collides with every other, and
lookup accuracy collapses for a reason that will take you an hour to find.

```python
scored.sort(key=lambda h: (-h.score, h.doc_id))
```

**What to notice:** the secondary sort key. Ties are common with TF-IDF over short
documents. Without a fixed rule for breaking ties, the number moves between runs.

Guard the real failures rather than assuming they cannot happen:

```python
if not documents:
    raise ValueError("Cannot build an index over zero documents")
if top_k < 1:
    raise ValueError("top_k must be at least 1")
```

---

## Step 5 — Turn search results into minutes (`src/baseline.py`)

```python
def answer_one(index, question, top_k=5, seconds_per_document=45.0, fallback_documents=12):
    hits = index.search(question.text, top_k=top_k)
    rank = None
    for position, hit in enumerate(hits, start=1):
        if hit.doc_id == question.answer_doc_id:
            rank = position
            break
    reads = rank if rank is not None else fallback_documents
    return QuestionOutcome(..., seconds_to_answer=reads * seconds_per_document)
```

**What to notice:** every assumption is a named parameter with a default, not a
literal buried in the function. When the VP of Claims says "45 seconds is
generous," you change one argument and rerun, in the meeting.

Report the split, not just the total:

```python
lookups = [o for o in outcomes if o.kind == "lookup"]
concepts = [o for o in outcomes if o.kind == "concept"]
```

**What to notice:** this is the single most important line in the lesson. The
aggregate number is 57% and it describes nothing. The two halves are 100% and 15%,
and they imply completely different projects.

---

## Step 6 — Produce the document you hand over (`src/scope.py`)

```python
SuccessCriterion(
    name="Answer found in top 5",
    baseline=f"{report.accuracy_at_5:.0%}",
    target=f"{TARGET_ACCURACY_AT_5:.0%}",
    measured_by="The 40-question set in tests/, rerun on every change.",
)
```

**What to notice:** `baseline` is formatted from the report. It is never typed by
hand. A test asserts this, because a hard-coded baseline that drifts from the
measurement is the exact failure this whole lesson exists to prevent.

---

## Step 7 — Tests that exercise real failures

The documents come out the same every time, so nothing here needs a fake. That is worth saying
plainly: if your test suite is mostly `MagicMock`, you are testing your
assumptions about the system rather than the system.

```python
def test_unanswerable_question_falls_back_and_is_not_found(self, index) -> None:
    q = Question(
        question_id="Q-X",
        text="Which claim involved a meteorite strike on the conservatory?",
        answer_doc_id="C-9999-NOT",
        kind="concept",
    )
    outcome = answer_one(index, q, top_k=5)
    assert outcome.rank is None
    assert outcome.seconds_to_answer == 12 * 45.0
```

Then the invariants that catch a broken instrument:

```python
def test_accuracy_is_monotonic_in_k(self, measured) -> None:
    report, _ = measured
    assert report.accuracy_at_1 <= report.accuracy_at_3 <= report.accuracy_at_5

def test_keyword_search_is_strong_on_identifier_lookups(self, measured) -> None:
    report, _ = measured
    assert report.accuracy_lookup >= 0.90
```

**What to notice:** the second one asserts the baseline is *good*. It fails if a
future change accidentally turns the current process into a strawman, which would
make every later comparison flattering and worthless.

---

## Step 8 — Check that everything passes

```bash
make check
```

```
43 passed
Required test coverage of 90% reached. Total coverage: 98.91%
Success: no issues found in 14 source files
All checks passed!
Lesson 1 green.
```

If `make run` prints numbers different from the article, check your seed. The
default is `20260908` and the whole point of seeding is that your output matches.

---

## Step 9 — Write the file you send

```bash
make write   # writes scoping-pack.md
```

Read it as the customer would. If any number in it cannot be traced to something
the code measured, that number does not belong in the document.

---

## Four ways to get this wrong

Four mistakes worth naming, because each one silently invalidates the result.

| Mistake | What happens |
|---|---|
| Two claims described the same way | Those questions get several correct answers, and accuracy stops meaning anything |
| Splitting words on hyphens | Claim numbers all look alike, lookups collapse, and the cause is not obvious |
| Reporting only the aggregate | 57% hides a solved half and an unsolved half, and you scope the wrong project |
| Typing a number into the handover document | It drifts away from what the code measured, which is the failure this lesson is about |

---

## Bar check

Set a timer for 45 minutes. Take this ask:

> "Our support team is drowning. Can AI help them close tickets faster?"

Produce numeric success criteria with a measurement method, and a five-day plan.
You may not write any model code. You are done when someone could disagree with a
specific number in your document.
