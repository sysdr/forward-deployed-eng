"""Builds the golden set: questions paired with the fact a right answer contains.

The word "golden" just means agreed. This is the set of questions the customer
signed off as representative, with the answers they consider correct. It is a
customer artifact that happens to live in your repository.

Ground truth is free here because the corpus generator knows what it wrote. On a
real engagement you spend an hour with the adjusters instead, which is the
highest-value hour of the whole project: it converts "make it better" into a
number you both agreed on.
"""
from __future__ import annotations

from src.corpus import build_corpus, build_questions
from src.models import Claim, Document, EvalCase, MatchKind


def build_golden_set(
    n_claims: int = 200, seed: int = 20260908
) -> tuple[list[EvalCase], list[Document], list[Claim]]:
    """Return eval cases alongside the corpus they were derived from."""
    claims, documents = build_corpus(n_claims=n_claims, seed=seed)
    questions = build_questions(claims, seed=seed)
    by_id = {c.claim_id: c for c in claims}
    doc_text = {d.doc_id: d.text for d in documents}

    cases: list[EvalCase] = []
    for q in questions:
        claim_id = q.answer_doc_id.rsplit("-", 1)[0]
        claim = by_id[claim_id]

        if q.kind == "concept":
            # "Which claim involved ...?" -> the claim identifier.
            expected, match = claim.claim_id, MatchKind.CONTAINS
        elif q.text.startswith("What is the reserve"):
            if claim.reserve_amount is None:
                # A genuinely unanswerable question. Keeping these is the point:
                # a system that invents a reserve is worse than one that says no.
                expected, match = "not yet established", MatchKind.CONTAINS
            else:
                expected, match = f"{claim.reserve_amount:,.2f}", MatchKind.NUMERIC
        elif q.text.startswith("What is the deductible"):
            expected = _deductible_from(doc_text[q.answer_doc_id])
            match = MatchKind.NUMERIC
        else:
            expected, match = claim.adjuster, MatchKind.CONTAINS

        cases.append(
            EvalCase(
                case_id=q.question_id,
                question=q.text,
                kind=q.kind,
                answer_doc_id=q.answer_doc_id,
                expected=expected,
                match=match,
            )
        )

    cases.extend(_edge_cases(claims, doc_text))
    return cases, documents, claims


def _edge_cases(claims: list[Claim], doc_text: dict[str, str]) -> list[EvalCase]:
    """Cases chosen on purpose, because sampling will not find them.

    The first draft of this lesson sampled 40 questions at random and, by luck,
    not one landed on a claim whose reserve was never set. The eval therefore
    could not tell the difference between a system that says "not established"
    and one that invents a number. A golden set is curated, not sampled: you add
    the cases that would embarrass you, whether or not chance offers them.
    """
    extra: list[EvalCase] = []

    missing = next((c for c in claims if c.reserve_amount is None), None)
    if missing is not None:
        extra.append(
            EvalCase(
                case_id="Q-E000",
                question=f"What is the reserve amount on claim {missing.claim_id}?",
                kind="lookup",
                answer_doc_id=f"{missing.claim_id}-NOT",
                expected="not yet established",
                match=MatchKind.CONTAINS,
            )
        )

    # A claim that does not exist. The only correct answer is a refusal, and the
    # scorer treats the refusal itself as the expected fact.
    known = {c.claim_id for c in claims}
    absent = next(f"C-{n}" for n in range(9000, 9100) if f"C-{n}" not in known)
    extra.append(
        EvalCase(
            case_id="Q-E001",
            question=f"What is the reserve amount on claim {absent}?",
            kind="lookup",
            answer_doc_id="__none__",
            expected="does not contain the answer",
            match=MatchKind.CONTAINS,
        )
    )
    return extra


def _deductible_from(policy_text: str) -> str:
    """Pull the deductible out of a policy declaration page."""
    marker = "deductible "
    start = policy_text.lower().index(marker) + len(marker)
    end = policy_text.index(".", start)
    return policy_text[start:end].strip()
