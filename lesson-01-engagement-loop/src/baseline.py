"""Measures the current state.

The output of this module is the only thing that turns "make claims faster"
into a sentence you can hold someone to.

Time to answer is modelled, not stopwatched, and the model is stated openly:
an adjuster reads down the result list until the answering document appears.
Each document costs `seconds_per_document`. If the answer never appears in the
top k, they fall back to browsing the claim folder by hand, which costs
`fallback_documents` reads.

Every one of those assumptions is arguable, which is the point. You put the
number in front of the customer and let them argue it down before you build
anything on top of it.
"""
from __future__ import annotations

import statistics

from src.models import BaselineReport, Document, Question, QuestionOutcome
from src.search import KeywordIndex

SECONDS_PER_DOCUMENT = 45.0
FALLBACK_DOCUMENTS = 12


def answer_one(
    index: KeywordIndex,
    question: Question,
    top_k: int = 5,
    seconds_per_document: float = SECONDS_PER_DOCUMENT,
    fallback_documents: int = FALLBACK_DOCUMENTS,
) -> QuestionOutcome:
    """Run one question through the current process and time the result."""
    hits = index.search(question.text, top_k=top_k)
    rank: int | None = None
    for position, hit in enumerate(hits, start=1):
        if hit.doc_id == question.answer_doc_id:
            rank = position
            break
    reads = rank if rank is not None else fallback_documents
    return QuestionOutcome(
        question_id=question.question_id,
        kind=question.kind,
        rank=rank,
        seconds_to_answer=reads * seconds_per_document,
    )


def percentile_index(n: int, q: float) -> int:
    """Index of the qth percentile in a sorted list of length n, clamped.

    Nearest-rank on a small sample. With 40 questions the p90 is the 36th
    value, and saying so beats implying a precision the sample cannot carry.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    return min(n - 1, int(round(q * (n - 1))))


def _accuracy(outcomes: list[QuestionOutcome], within: int) -> float:
    if not outcomes:
        return 0.0
    hit = sum(1 for o in outcomes if o.rank is not None and o.rank <= within)
    return round(hit / len(outcomes), 4)


def measure(
    documents: list[Document],
    questions: list[Question],
    top_k: int = 5,
    seconds_per_document: float = SECONDS_PER_DOCUMENT,
    fallback_documents: int = FALLBACK_DOCUMENTS,
) -> tuple[BaselineReport, list[QuestionOutcome]]:
    """Measure the current process over the whole question set."""
    if not questions:
        raise ValueError("Cannot measure a baseline with no questions")
    index = KeywordIndex(documents)
    outcomes = [
        answer_one(index, q, top_k, seconds_per_document, fallback_documents)
        for q in questions
    ]
    seconds = sorted(o.seconds_to_answer for o in outcomes)
    lookups = [o for o in outcomes if o.kind == "lookup"]
    concepts = [o for o in outcomes if o.kind == "concept"]

    report = BaselineReport(
        corpus_documents=len(documents),
        questions_asked=len(questions),
        seconds_per_document=seconds_per_document,
        fallback_documents=fallback_documents,
        accuracy_at_1=_accuracy(outcomes, 1),
        accuracy_at_3=_accuracy(outcomes, 3),
        accuracy_at_5=_accuracy(outcomes, 5),
        accuracy_lookup=_accuracy(lookups, top_k),
        accuracy_concept=_accuracy(concepts, top_k),
        p50_seconds=round(statistics.median(seconds), 2),
        p90_seconds=round(seconds[percentile_index(len(seconds), 0.9)], 2),
        mean_seconds=round(statistics.fmean(seconds), 2),
        fallback_rate=round(
            sum(1 for o in outcomes if o.rank is None) / len(outcomes), 4
        ),
    )
    return report, outcomes

