# The Engagement Loop: Turning a Vague Ask into a Measured Baseline

*The customer says "use AI to speed up claims," and the fastest way to fail is to believe you have been given a specification.*

| | |
|---|---|
| **Series** | AI Forward Deployed Engineer |
| **Arc** | 1 · The Engagement Loop |
| **Lesson** | 1 of 35 — the stage every later lesson depends on |
| **Audience** | Engineers · Architects · PMs · QA · SRE · Data engineers |
| **Read time** | 12 min |
| **Build time** | 90 min |
| **Prerequisites** | Python 3.12. Nothing else. |
| **Cost to run** | Zero. No API key, no service, no network call. |
| **Bar check** | Vague ask to numeric success criteria in 45 minutes |

---

## The problem

Between 86% and 89% of enterprise AI pilots never reach production, and the reason is not that the models are bad. Across the studies, the largest single cause is unclear success criteria, and the most-cited blocker by leaders is missing evaluation. Only after those come tooling and data access.

Read that again, because it decides what this course teaches first. The dominant failure mode is not a modelling problem or an infrastructure problem. It is that nobody wrote down what "better" would mean, in numbers, before the work started.

So this lesson builds no AI at all. It builds the thing that has to exist before AI is worth building.

---

## The customer

Every lesson in this course works on the same engagement.

> **Meridian Mutual.** Regional property insurer, 2,400 employees. Claims adjusters spend a large share of their day reading documents scattered across a document store nobody has indexed. The VP of Claims wants "AI to speed up claims." The CISO has never allowed claim data to leave the network. Nobody can tell you what "faster" means.

Your job this week is to fix that last sentence, and to fix it with a measurement rather than a meeting.

---

## What a properly scoped job looks like

Name these, because you will use them in every engagement you ever run. An engagement that is missing any one of them is not scoped, however confident everyone sounds.

| Property | What it means |
|---|---|
| **Restated** | The ask is rewritten as an observable behaviour, not an aspiration. "Speed up claims" becomes "an adjuster asks a question and gets to the answering document." |
| **Baselined** | You measured the current state before you changed it. Without this, every later improvement is an assertion. |
| **Numeric** | Every success criterion has a number, a unit, and a method. "Better retrieval" is not a criterion. |
| **Falsifiable** | Kill criteria are written down before anyone is invested, and they are specific enough to trigger. |
| **Bounded** | What you are not doing is written down, in the same document, with the same weight. |

↑ **Diagram 1** shows where these live: stages one through three of the seven-stage loop, and the dashed line is the exit that kill criteria make possible.

---

## Why you measure before you build

Here is the trap. "Speed up claims" sounds like a goal. It is actually four unanswered questions: which task, for whom, measured how, and compared to what.

You cannot answer any of them by thinking harder. You answer them by building the smallest possible instrument and pointing it at the current process.

**The non-obvious part:** you do not need the customer's real data for this to be useful. Made-up documents that copy the *shape* of the mess give you a starting number today, on your laptop, weeks before the security review lets you near the real files. When access arrives you point the same code at the real documents. The number changes. The argument does not.

That is why this lesson generates its own documents. It is also why the generator uses a fixed seed, so it produces exactly the same documents every time. A number measured in lesson 1 has to be comparable to one measured in lesson 15, or the whole course is measuring nothing.

---

## Building something to measure with

Four pieces, none of them clever.

### Documents as messy as the real ones

Real claim files are not clean, and a corpus that is clean will flatter your search. `src/corpus.py` produces 200 claims and 750 documents carrying the specific awkwardness of real insurance records: three date formats because three systems wrote them, reserve amounts missing on roughly one claim in seven, adjuster names spelled inconsistently, and theft claims that have no contractor estimate because nobody estimates a stolen laptop.

The important mess is subtler. Each loss is described twice. The adjuster's file says `burst pipe saturated the upstairs bathroom, damaging hardwood flooring`. A person asking about it says `water leak soaked the second floor bathroom, harming timber floorboards`. Same event, one shared word.

```python
ACTIONS: list[tuple[str, str, str]] = [
    ("burst pipe saturated", "water leak soaked", "water"),
    ("storm stripped shingles from", "gale tore roofing off", "wind"),
]
```

**What to notice:** the action, location and object are combined by index, giving 8 × 6 × 6 = 288 different losses. That is more than the 200 claims, which is what guarantees every question has exactly one correct answer. If two claims shared a description, the accuracy number would quietly be a lie, so `tests/test_corpus.py` checks that they never do.

### Questions we already know the answers to

Forty questions, in two kinds that behave completely differently:

- **Lookup**, which contains an identifier: *"What is the reserve amount on claim C-1042?"*
- **Concept**, which does not: *"Which claim involved water leak soaked the second floor bathroom?"*

We know the right answer for free, because the generator knows which document it put the answer in. Nobody has to sit and label anything.

### How they search today

`src/search.py` is TF-IDF keyword search. It is not a strawman. Weighting terms by rarity is what most enterprise document stores actually do, and on identifier lookups it is close to unbeatable.

```python
self._idf: dict[str, float] = {
    term: math.log((n + 1) / (df + 1)) + 1.0 for term, df in appearances.items()
}
```

**What to notice:** ties break on `doc_id`, not arbitrarily. Without that, two runs of the same baseline produce different numbers and you spend a morning wondering what changed.

### Turning search results into minutes

```python
reads = rank if rank is not None else fallback_documents
seconds_to_answer = reads * seconds_per_document
```

An adjuster reads down the results until the answer appears. Each document costs 45 seconds. If the answer never appears, they browse the folder by hand, which costs 12 reads.

**The non-obvious part:** every one of those numbers is arguable, and that is the feature. You put the model in front of the VP of Claims and they say "45 seconds is generous, our people skim." Good. Now they are arguing about the instrument instead of about whether the project is working, and whatever number you settle on is one they chose. A stopwatch study would have been more accurate and far less useful, because it would have taken three weeks and produced a number they had no stake in.

↑ **Diagram 2** shows the shape of the result: one search, two groups of questions, two completely different outcomes.

---

## Run it

```bash
make install
make run
```

```
Corpus:     750 documents across 200 claims
Questions:  40

Current process — keyword search over the document store
  answer in top 1                    18%
  answer in top 3                    55%
  answer in top 5                    57%
    questions with a claim number   100%
    questions in plain language      15%

  median time to answer             2.25 min
  p90 time to answer                9.00 min
  mean time to answer                4.8 min
  fell back to manual review         42%
```

---

## What the numbers say

That output is the deliverable, and the shape of it is the finding.

Keyword search answers **100%** of questions that contain a claim number, and **15%** of questions phrased the way a person actually speaks. The overall figure of 57% is the average of a solved problem and an unsolved one, which is why reporting the average alone would have hidden the entire result.

This changes what you propose. You are not replacing the customer's search. You are adding something that handles the half it cannot reach, and the honest version of that sentence is worth more to a VP than a demo.

Two other numbers matter. The median time to answer is 2.25 minutes but the mean is 4.8, and a mean above the median means a long tail of failures dragging the average up. And 42% of questions retrieve nothing useful at all, which is where that tail comes from.

**The non-obvious part:** the answer is first in the list only 18% of the time but in the top five 57% of the time, and part of that gap is a fault in our measuring tool rather than a fact about the problem. Term frequency is divided by document length, so a 20-word photo manifest outranks a 60-word set of adjuster notes containing the same claim number. `tests/test_search.py` documents this deliberately. Finding the fault in your own measuring tool before the customer does is most of what separates a real baseline from a number.

---

## What it costs to run

Zero, and that is a design constraint rather than a happy accident. The documents are generated, the search index is a dictionary in memory, and the time model is multiplication. The whole baseline runs in under a second on a laptop with no network connection.

This matters beyond your wallet. On day one of an engagement you have no credentials, no VPN, and no data. Work that requires none of those is work you can do while the access request sits in a queue.

---

## The document you hand over

`src/scope.py` turns the measured report into the document you send. Every baseline in it is read from the report rather than typed in, which is enforced by a test.

| Criterion | Today | Target | Measured by |
|---|---|---|---|
| Answer found in top 5 | 57% | 90% | The 40-question set, rerun on every change |
| Answer found without a claim number | 15% | 90% | The concept subset of the same set |
| Median time to answer | 2.25 min | under 1 min | Rank × 45s per document read |
| Questions falling back to manual review | 42% | under 10% | Share where no result contained the answer |

And the part most engineers omit:

> **We stop if** concept accuracy does not exceed 75% after two weeks · median time to answer does not improve by at least half · cost per answered question exceeds the adjuster minutes it saves · the documents cannot be indexed without moving claim data off Meridian's network.

**The non-obvious part:** kill criteria are the section customers trust most and engineers write least. Writing down what would make you stop is what makes the rest of the document credible, because it proves the plan was not reverse-engineered from a decision to build something.

---

## What you just built

- A **repeatable set of documents** shaped like real claim files, so every later lesson measures against the same thing
- A **40-question set** whose right answers are known in advance, with nobody labelling anything
- An **honest version of the search they use today**, strong where keyword search is genuinely strong
- A **stated time model** the customer can argue with, which is the point
- A **scoping pack** whose every number traces to a measurement, with kill criteria and an out-of-scope list
- **43 tests at 99% coverage**, none of them faked, because documents that come out the same every time need no fakes

---

## Five things to remember

1. **The average hid the finding.** 57% overall was two populations: 100% and 15%. Report the split or you will scope the wrong project.
2. **Made-up documents are a schedule move, not a compromise.** They give you a number weeks before the security review lets you touch real data.
3. **Say the time model out loud.** A number the customer argued down is a number they own. A number from a stopwatch study is a number they can dismiss.
4. **Check your own measuring tool for faults.** The top-1 number was dragged down by short documents winning, not by the questions being hard.
5. **Kill criteria are a credibility device.** They cost nothing to write in week one and are almost impossible to add in week six.

---

## Where this fits

Lesson 2 makes this code production-shaped: typed boundaries, structured logs, retries, and tests that survive a real network. Lesson 3 turns the 40-question set into a proper evaluation suite with a CI gate, and from there nothing in this course ships without one. Lesson 4 puts a cost on every operation. By lesson 15 you will run this same measurement against a retrieval system that closes the 15% gap, and the comparison will be valid because the instrument never changed.

---

## Your FDE interview edge

The highest-weighted round in a forward deployed engineering loop is an ambiguous case study, and it has the lowest pass rate of any stage. A customer hands you a vague problem and you have 45 minutes to decompose it.

Candidates fail that round by starting to design. What passes is restating the ask as something observable, naming what you would measure, stating the assumptions in your measurement out loud, and saying what would make you stop. That is this lesson, performed rather than written.

**Bar check:** take any one-paragraph ask and produce numeric success criteria and a five-day plan in 45 minutes.

---

## Next

**Lesson 2 — Production Python for AI Engineers.** The generator works, but it would not survive a real document store. Nothing checks the shape of what comes back, nothing records what happened, nothing retries a dropped connection, and no log tells you which run a failure came from.
