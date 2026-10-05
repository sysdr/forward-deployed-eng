"""Generates Meridian Mutual's claim corpus.

Deterministic: the same seed always produces the same corpus, so a baseline
measured today is comparable to one measured in lesson 15. That property is
the whole reason this is generated rather than downloaded.

The mess is deliberate and modelled on real claim files:
  - three date formats, because three systems wrote these records
  - reserve amounts missing on roughly one claim in seven
  - adjuster names spelled inconsistently
  - narrative text that describes a loss without ever naming it the way an
    adjuster would search for it

That last one is the important one. It is why keyword search scores badly on
concept questions in `baseline.py`, and it is the gap the rest of the course closes.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from src.models import Claim, DocKind, Document, Peril, Question

# Each claim's loss is described twice: once the way the adjuster writes it up,
# and once the way the claimant would ask about it. The two vocabularies are
# chosen to share no words. Combining an action, a location and an object gives
# 8 x 6 x 6 = 288 unique losses, so every concept question has exactly one
# correct answer document even at 200 claims.
ACTIONS: list[tuple[str, str, str]] = [
    ("burst pipe saturated", "water leak soaked", "water"),
    ("sewer backup flooded", "drain reversal submerged", "water"),
    ("storm stripped shingles from", "gale tore roofing off", "wind"),
    ("mature oak fell across", "tree collapse landed on", "wind"),
    ("range fire left smoke residue in", "cooking blaze spread soot through", "fire"),
    ("electrical fault scorched", "wiring failure burned", "fire"),
    ("forced entry removed goods from", "break in took belongings from", "theft"),
    ("side door jimmied, tools taken from", "rear entrance prised, equipment stolen from", "theft"),
]

# Locations survive paraphrase: people name rooms the same way the file does.
# Objects overlap partially. Actions do not overlap at all, because that is the
# part a claimant describes in their own words. The result is a query that
# shares real vocabulary with its document without being a keyword match --
# which is exactly why keyword search scores badly but not zero.
LOCATIONS: list[tuple[str, str]] = [
    ("the upstairs bathroom", "the second floor bathroom"),
    ("the finished basement", "the lower level basement"),
    ("the south elevation", "the sunward elevation"),
    ("the detached garage", "the separate garage"),
    ("the attic junction box", "the loft junction box"),
    ("the ground floor den", "the main level den"),
]

OBJECTS: list[tuple[str, str]] = [
    ("hardwood flooring", "timber floorboards"),
    ("plaster ceiling", "gypsum overhead"),
    ("cabinetry and worktops", "fitted units"),
    ("framing members", "structural timbers"),
    ("electronics and audio equipment", "media devices"),
    ("insulation batts", "thermal wadding"),
]


def _loss(i: int) -> dict[str, str]:
    """Deterministic unique loss for claim index i.

    Strides are coprime with the list lengths so the triple does not repeat
    before 288 claims.
    """
    action_doc, action_q, peril = ACTIONS[i % len(ACTIONS)]
    loc_doc, loc_q = LOCATIONS[(i // len(ACTIONS)) % len(LOCATIONS)]
    obj_doc, obj_q = OBJECTS[(i // (len(ACTIONS) * len(LOCATIONS))) % len(OBJECTS)]
    return {
        "peril": peril,
        "doc": f"{action_doc} {loc_doc}, damaging {obj_doc}",
        "query": f"{action_q} {loc_q}, harming {obj_q}",
    }


ADJUSTERS = ["R. Okonkwo", "R Okonkwo", "M. Halvorsen", "M Halvorsen", "T. Bhatt", "T Bhatt"]
STATUSES = ["open", "open", "open", "reopened", "closed", "pending review"]


def _format_date(d: date, style: int) -> str:
    """Three systems, three formats. Nobody normalised them."""
    if style == 0:
        return d.isoformat()
    if style == 1:
        return d.strftime("%d/%m/%Y")
    return d.strftime("%B %-d, %Y")


def build_corpus(
    n_claims: int = 200, seed: int = 20260908
) -> tuple[list[Claim], list[Document]]:
    """Return claims and their documents. Deterministic for a given seed."""
    rng = random.Random(seed)
    claims: list[Claim] = []
    docs: list[Document] = []
    start = date(2025, 9, 1)

    for i in range(n_claims):
        scenario = _loss(i)
        claim_id = f"C-{1000 + i}"
        policy_id = f"P-{4000 + (i * 7) % 900}"
        loss_date = start + timedelta(days=rng.randint(0, 330))
        date_style = rng.randint(0, 2)
        adjuster = rng.choice(ADJUSTERS)
        # Roughly one claim in seven has no reserve set. This is real.
        reserve = None if rng.random() < 0.14 else round(rng.uniform(1_800, 96_000), 2)
        deductible = rng.choice([500, 1000, 2500, 5000])

        claims.append(
            Claim(
                claim_id=claim_id,
                policy_id=policy_id,
                date_of_loss=loss_date,
                peril=Peril(scenario["peril"]),
                status=rng.choice(STATUSES),
                reserve_amount=reserve,
                adjuster=adjuster,
            )
        )

        shown_date = _format_date(loss_date, date_style)

        docs.append(
            Document(
                doc_id=f"{claim_id}-POL",
                claim_id=claim_id,
                kind=DocKind.POLICY,
                text=(
                    f"Policy declaration page. Policy {policy_id}. "
                    f"Named insured on file. Dwelling coverage limit "
                    f"{rng.choice([250_000, 400_000, 650_000, 900_000]):,}. "
                    f"All perils deductible {deductible}. "
                    f"Policy period effective through renewal."
                ),
            )
        )

        reserve_text = (
            f"Reserve set at {reserve:,.2f}."
            if reserve is not None
            else "Reserve not yet established pending inspection."
        )
        docs.append(
            Document(
                doc_id=f"{claim_id}-NOT",
                claim_id=claim_id,
                kind=DocKind.NOTES,
                text=(
                    f"Adjuster notes for claim {claim_id}. Handled by {adjuster}. "
                    f"Date of loss {shown_date}. "
                    f"Insured reports {scenario['doc']}. "
                    f"Field inspection confirms the reported cause and extent. "
                    f"{reserve_text} "
                    f"Coverage appears to apply subject to policy terms."
                ),
            )
        )

        if scenario["peril"] != "theft":
            total = round(rng.uniform(2_400, 78_000), 2)
            docs.append(
                Document(
                    doc_id=f"{claim_id}-EST",
                    claim_id=claim_id,
                    kind=DocKind.ESTIMATE,
                    text=(
                        f"Contractor estimate for claim {claim_id}. "
                        f"Scope covers remediation, materials and labour. "
                        f"Estimate total {total:,.2f}. "
                        f"Quoted by an approved vendor. Valid thirty days."
                    ),
                )
            )

        docs.append(
            Document(
                doc_id=f"{claim_id}-PHO",
                claim_id=claim_id,
                kind=DocKind.PHOTOS,
                text=(
                    f"Photo manifest for claim {claim_id}. "
                    f"{rng.randint(4, 30)} images captured on site. "
                    f"Overview, detail and measurement shots included."
                ),
            )
        )

    return claims, docs


def build_questions(
    claims: list[Claim], seed: int = 20260908, n_per_kind: int = 20
) -> list[Question]:
    """Build a question set with ground truth known by construction.

    Two kinds, because they behave completely differently under keyword search:

      lookup  — the question contains an identifier that appears verbatim in
                the answering document. Keyword search is good at these.
      concept — the question describes the loss in a claimant's words, which
                share almost no vocabulary with the adjuster's write-up.
                Keyword search is bad at these, and most real questions are these.
    """
    rng = random.Random(seed)
    questions: list[Question] = []
    pool = list(claims)

    for i, claim in enumerate(rng.sample(pool, min(n_per_kind, len(pool)))):
        template = i % 3
        if template == 0:
            text = f"What is the reserve amount on claim {claim.claim_id}?"
            doc = f"{claim.claim_id}-NOT"
        elif template == 1:
            text = f"What is the deductible on policy {claim.policy_id}?"
            doc = f"{claim.claim_id}-POL"
        else:
            text = f"Who is the adjuster handling claim {claim.claim_id}?"
            doc = f"{claim.claim_id}-NOT"
        questions.append(
            Question(
                question_id=f"Q-L{i:03d}", text=text, answer_doc_id=doc, kind="lookup"
            )
        )

    concept_claims = rng.sample(pool, min(n_per_kind, len(pool)))
    for i, claim in enumerate(concept_claims):
        idx = int(claim.claim_id.split("-")[1]) - 1000
        scenario = _loss(idx)
        questions.append(
            Question(
                question_id=f"Q-C{i:03d}",
                text=f"Which claim involved {scenario['query']}?",
                answer_doc_id=f"{claim.claim_id}-NOT",
                kind="concept",
            )
        )

    return questions
