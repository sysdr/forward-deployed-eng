# Build it: a scope policy and a guard in front of someone else's repository

You are building four things: a written policy, a checker, a set of proposed
changes whose right answers you already know, and a score. The score is the point.
By the end you will have a number for how much of "stay in scope" a program can
actually enforce.

The guard path runs offline: no model, no network, no key. Lesson 4's priced
commands (`make costs`) are still in the tree and need Ollama if you use them.

---

## Step 0 — Check you can run it

```bash
python3 --version     # 3.12 or newer
```

Lesson 4's folder is the starting point. Copy it, or run the scaffold:

```bash
tools/scaffold-lesson.sh 05 shipping-with-agents --from lessons/lesson-04-what-it-costs
```

That carries `src/` and `tests/` forward and installs the venv.

**What to notice:** the carried `src/main.py` is the only thing that exercises
`corpus.py`, `search.py`, `evaluate.py` and `goldenset.py` in the test run. Keep
it. Step 6 explains what happens if you do not.

---

## Step 1 — Install

From this lesson folder:

```bash
cd lesson-05-shipping-with-agents   # or lessons/lesson-05-shipping-with-agents
make install
```

`requirements.txt` is unchanged from lesson 4. This lesson adds no dependency,
which is also one of the rules the guard enforces.

### Optional — Ollama for `make costs`

The scope guard does not need a model. If you want the carried lesson-4 budget
run against a real model, point the client at your Ollama host:

```bash
export OLLAMA_HOST=http://192.168.1.10:11434   # default in src/llm.py
curl -sS "$OLLAMA_HOST/api/tags"               # should list models
make costs MODEL=llama3.2:3b
```

`OllamaClient` reads `OLLAMA_HOST`. If unset, it uses `http://192.168.1.10:11434`.
A host without a scheme is fine (`192.168.1.10:11434`); `http://` is added.

---

## Step 2 — `src/policy.py`: write the agreement down as a file

The agreement about what you may change is usually a sentence in a kickoff call,
which means it is not an agreement. A policy object is the same sentence in a form
a program can check.

```python
class ScopePolicy(BaseModel):
    engagement: str
    may_edit: list[str] = Field(default_factory=list)
    never_touch: list[str] = Field(default_factory=list)
    may_delete: bool = False
    may_add_dependencies: bool = False
    max_files_per_change: int = 12
    forbidden_content: list[str] = Field(default_factory=list)

    def allows_path(self, path: str) -> bool:
        if any(fnmatch.fnmatch(path, p) for p in self.never_touch):
            return False
        return any(fnmatch.fnmatch(path, p) for p in self.may_edit)


MERIDIAN = ScopePolicy(
    engagement="Meridian Mutual claims assistant",
    may_edit=[
        "services/claims-assistant/**", "docs/claims-assistant/**", "tests/claims_assistant/**",
    ],
    never_touch=[
        "**/secrets/**", "**/.env*", "infra/**", ".github/workflows/**",
        "services/billing/**", "services/policy-admin/**",
    ],
    forbidden_content=["BEGIN PRIVATE KEY", "AKIA", "password =", "api_key ="],
)
```

**What to notice:** the two lists overlap on purpose and `never_touch` is checked
first. A path can be inside `services/**` and still be refused. If you check
`may_edit` first and return early, `services/billing/ledger.py` becomes editable
the moment someone broadens a pattern, and nobody notices for a month.

The default for `may_edit` is an empty list, so a policy nobody has filled in
allows nothing. Test it:

```python
def test_an_empty_may_edit_allows_nothing(self) -> None:
    assert not ScopePolicy(engagement="empty").allows_path("anything.py")
```

---

## Step 3 — `src/change.py`: the shape a proposal arrives in

Deliberately not a git diff. An agent proposes edits, and you want to check them
in the same shape whether they came from a patch file, a pull request, or an agent
holding them in memory.

```python
class Operation(StrEnum):
    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"


class FileChange(BaseModel):
    path: str
    operation: Operation
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)


class ProposedChange(BaseModel):
    title: str
    asked_for: str
    files: list[FileChange]

    @computed_field
    @property
    def file_count(self) -> int:
        return len(self.files)

    def added_text(self) -> str:
        return "\n".join(line for f in self.files for line in f.added_lines)
```

**What to notice:** `asked_for` sits next to `title`. Nothing in the guard reads
it. It is there because the reviewer needs it and because step 5 measures exactly
what happens when only a person can compare the two.

`added_text()` joins added lines only. A credential the change *removes* is not a
credential the change introduces, and scanning the whole file body would flag the
cleanup as the crime.

mypy cannot see through pydantic's `@computed_field` stacked on `@property`, so
`pyproject.toml` disables `prop-decorator` for this module and `src.models`:

```toml
[[tool.mypy.overrides]]
module = ["src.models", "src.change"]
disable_error_code = ["prop-decorator"]
```

---

## Step 4 — `src/guard.py`: five checks that run before a change lands

Every check is mechanical, which is the point. You will not read four hundred
lines of agent output carefully at five on a Thursday, and neither will the
customer's reviewer. What you will do is run this.

```python
def check(change: ProposedChange, policy: ScopePolicy) -> GuardResult:
    found: list[Violation] = []

    for f in change.files:
        if not policy.allows_path(f.path):
            found.append(Violation(kind="out-of-scope-path",
                                   detail="not inside what was agreed", path=f.path))
        if f.operation is Operation.DELETE and not policy.may_delete:
            found.append(Violation(
                kind="deletion",
                detail="the agreement did not include deleting files", path=f.path))
        if not policy.may_add_dependencies and f.path.endswith(DEPENDENCY_FILES) and f.added_lines:
            found.append(Violation(
                kind="new-dependency",
                detail="a dependency is someone else's supply chain", path=f.path))

    if change.file_count > policy.max_files_per_change:
        found.append(Violation(
            kind="too-many-files",
            detail=f"{change.file_count} files, the agreement says {policy.max_files_per_change}"))

    body = change.added_text()
    for needle in policy.forbidden_content:
        if needle in body:
            found.append(Violation(kind="forbidden-content",
                                   detail=f"the change adds a line containing {needle!r}"))

    return GuardResult(title=change.title, violations=found)
```

**What to notice:** there is no early return. A change that touches a forbidden
path *and* adds a dependency reports both, because the person reading the output
needs the whole list, not the first thing that tripped. The test that holds this
in place:

```python
def test_every_check_runs_rather_than_stopping_at_the_first(self) -> None:
    change = _change(
        FileChange(path="infra/main.tf", operation=Operation.DELETE),
        _edit(f"{CLAIMS}/requirements.txt", "tenacity==9.0.0"),
    )
    assert check(change, MERIDIAN).kinds() == {
        "out-of-scope-path", "deletion", "new-dependency"}
```

The dependency check requires `f.added_lines`. Removing a pinned line from
`requirements.txt` is not pulling in new code, and flagging it teaches people to
ignore the guard.

---

## Step 5 — `src/scenarios.py`: changes whose right answer you already know

The guard is a measuring instrument, so it needs something to measure. Ten
proposed changes, each labelled by a person before the guard runs. The guard never
sees the label.

```python
class Kind(StrEnum):
    MECHANICAL = "mechanical"      # breaks a written rule
    SCOPE_CREEP = "scope-creep"    # breaks no written rule and is still wrong
    IN_SCOPE = "in-scope"          # exactly what the ticket said


class Scenario(BaseModel):
    change: ProposedChange
    kind: Kind
    expects: str | None = None   # for MECHANICAL, the violation kind the guard must report
    why: str = ""                # why a person would refuse it
```

Six mechanical ones, one per class the guard checks, plus a second path case so
you can tell `may_edit` and `never_touch` apart. Then the three that matter:

```python
def _creep_behaviour() -> Scenario:
    return Scenario(
        kind=Kind.SCOPE_CREEP,
        why="raising the retrieved-document count changes cost and answers for every user",
        change=ProposedChange(
            title="Fix the timeout, and raise top-k from 5 to 20",
            asked_for="Raise the document fetch timeout from 2s to 10s.",
            files=[
                _edit(f"{CLAIMS}/config.py",
                      "FETCH_TIMEOUT_SECONDS = 10",
                      "TOP_K = 20",
                      "CACHE_ANSWERS = True"),
            ],
        ),
    )
```

**What to notice:** one file, inside `may_edit`, no delete, no dependency, no
credential, three lines. Every written rule is satisfied. Two of those three lines
change what every user gets, and the third turns on caching, which changes what
they get when the data behind it moves.

The third creep case is the one that took the longest to see:

```python
FileChange(
    path=f"{CLAIMS}/answerer.py",
    operation=Operation.EDIT,
    added_lines=["    return self._model.answer(question)"],
    removed_lines=[
        "    if not self._policy.permits(question):",
        "        raise NotPermitted(question)",
    ],
)
```

The operation is `EDIT`, so the deletion check never fires. A permission check
left the codebase and no rule in the policy describes what happened.

The labels get tested too, because a mislabelled scenario silently changes the
lesson's number:

```python
def test_a_scope_creep_scenario_breaks_no_written_rule(self, scenario) -> None:
    result = check(scenario.change, MERIDIAN)
    assert result.allowed, f"expected clean, got {sorted(result.kinds())}"
```

---

## Step 6 — `src/main.py`: score it, and keep lesson 4's commands

Add the scoring below a marker comment. Do not replace the file.

```python
# ---------------------------------------------------------------------------
# Lesson 5 adds the scope guard. Everything above is carried from lesson 4
# unchanged, apart from the two new branches in main().
# ---------------------------------------------------------------------------


def is_right(scenario: Scenario, result: GuardResult) -> bool:
    if scenario.kind is Kind.MECHANICAL:
        return scenario.expects in result.kinds()
    if scenario.kind is Kind.SCOPE_CREEP:
        return not result.allowed
    return result.allowed  # in-scope: the right answer is to let it through
```

**Here is a real bug, and it cost twenty minutes.** The first version of this file
replaced lesson 4's `main.py` entirely with the guard report, and dropped lesson
4's `tests/test_main.py` along with it. `make test` still passed every assertion,
and coverage fell from 93% to 46%:

```
src/corpus.py       65     52    20%
src/evaluate.py     46     46     0%
src/goldenset.py    39     33    15%
src/search.py       38     38     0%
TOTAL              758    412    46%
```

Those four modules had no direct tests in lesson 4 either. `test_main.py` was
running them end to end through the priced report, and deleting one entry point
took four modules' coverage with it. The fix is the marker comment above: extend
the file, keep `--budget` and `--load`, and make the guard the default.

`--allow` adds one glob and nothing else, so you can see the policy is an input
rather than a hard-coded opinion:

```python
def widen(policy: ScopePolicy, path_glob: str) -> ScopePolicy:
    return policy.model_copy(update={"may_edit": [*policy.may_edit, path_glob]})
```

---

## Step 7 — Run the gates

```bash
make install   # once
make check     # tests + mypy + ruff — no model, no network
```

```
TOTAL                832     46    94%
Required test coverage of 90% reached. Total coverage: 94.47%
============================= 103 passed in 2.07s ==============================
./.venv/bin/python -m mypy src/ tests/ --ignore-missing-imports
Success: no issues found in 30 source files
./.venv/bin/python -m ruff check src/ tests/
All checks passed!
Lesson green.
```

If ruff complains about import spacing in a file you touched, leave two blank
lines after the last import before the first top-level definition.

---

## Step 8 — Produce the number

```bash
make run       # score every scenario
make widen     # same score with one path added to may_edit
```

Optional, only if Ollama is up (see Step 1):

```bash
make costs MODEL=llama3.2:3b
```

`make run` prints:

```
mechanical violations caught : 6 of 6
doing more than was asked    : 0 of 3
in-scope changes allowed     : 1 of 1
overall                      : 6 of 9 changes that should have been stopped

Got through, having satisfied every written rule:

  Add the log line, and restructure the answerer while there
      asked for : Add a log line recording how long an answer took.
      why bad   : the ticket was one log line; the change rewrites how answers are built

  Fix the timeout, and raise top-k from 5 to 20
      asked for : Raise the document fetch timeout from 2s to 10s.
      why bad   : raising the retrieved-document count changes cost and answers for every user

  Speed up the answer path
      asked for : Reduce time spent building an answer.
      why bad   : the validation was removed inside an edit, so nothing flags it as a deletion
```

Then show the policy is the input:

```bash
make widen
```

```
  widened by  may_edit += 'services/search-gateway/**'
...
Fix the retry helper in the shared gateway                   mechanical   nothing                           NO
Give the assistant more memory in production                 mechanical   out-of-scope-path                yes
...
mechanical violations caught : 5 of 6
```

One line added to `may_edit`, one row flipped, nothing else touched. The
`infra/terraform` row stays refused, because it is named in `never_touch` and no
amount of widening reaches it.

**A second real bug, and this one made a success criterion false.** The first
version of the out-of-scope scenario edited `services/billing/http.py`. That path
is in `never_touch`, so `--allow "services/billing/**"` changed nothing at all,
and the criterion "adding a path to the policy changes the result with no other
edit" could not be demonstrated. The fix was two scenarios instead of one: a
shared-gateway path that widening reaches, and an `infra/` path that it never
will. Both report `out-of-scope-path`; only one of them is negotiable, and until
they were separate that distinction was invisible.

---

## Where to go wrong

| Mistake | What it causes |
|---|---|
| Checking `may_edit` before `never_touch` | Widening one pattern quietly unlocks a path someone explicitly excluded. `test_never_touch_beats_may_edit` fails. |
| Returning at the first violation | The reviewer fixes the path, reruns, finds a dependency, fixes it, reruns. Three round trips for one change. |
| Scanning the whole file body for forbidden strings | Removing a leaked key gets flagged as adding one, and people stop reading the output. |
| Flagging any touch of `requirements.txt` | Deleting a pinned line is refused as a new dependency. Require `added_lines`. |
| Treating a clean guard result as approval | This is the whole lesson. 6 of 9 is the score, and the 3 are the expensive ones. |
| Deleting the carried entry point | Coverage falls to 46% while every test still passes, because four inherited modules were only reached through it. |

---

## Bar check

**Write the scope policy for an engagement you have not started. 20 minutes.**

Pick any repository you do not own. Produce a `ScopePolicy` with real path
patterns from that repository: what you may edit, what you must never touch, and
whether you may delete or add a dependency. Then write two proposed changes that
your policy refuses and one that it allows but you would still send back, and say
in one sentence who has to catch that third one.

You pass if the third change exists and you can name the person.
