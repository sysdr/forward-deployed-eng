"""Typed contracts for the engagement.

Every number the customer will eventually argue about lives in one of these
models. Making them explicit now is what stops "faster" from staying a word.
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class Peril(StrEnum):
    """What caused the loss. Real insurers carry dozens; four is enough here."""

    WIND = "wind"
    WATER = "water"
    FIRE = "fire"
    THEFT = "theft"


class DocKind(StrEnum):
    POLICY = "policy_declaration"
    NOTES = "adjuster_notes"
    ESTIMATE = "contractor_estimate"
    PHOTOS = "photo_manifest"


class Document(BaseModel):
    """One retrievable unit. In lesson 11 these become chunks; today they are files."""

    doc_id: str
    claim_id: str
    kind: DocKind
    text: str

    @computed_field
    @property
    def word_count(self) -> int:
        return len(self.text.split())


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    date_of_loss: date
    peril: Peril
    status: str
    reserve_amount: float | None = None  # genuinely missing on some claims
    adjuster: str


class Question(BaseModel):
    """A question an adjuster actually asks, with the document that answers it.

    `answer_doc_id` is ground truth by construction: the corpus generator put
    the answer in exactly that document. That is what makes scoring possible
    without a human labelling pass.
    """

    question_id: str
    text: str
    answer_doc_id: str
    kind: str  # "lookup" (an identifier) or "concept" (a description)


class RankedHit(BaseModel):
    doc_id: str
    score: float


class QuestionOutcome(BaseModel):
    """What happened when the current process tried to answer one question."""

    question_id: str
    kind: str
    rank: int | None  # 1-indexed position of the answer, None if not retrieved
    seconds_to_answer: float

    @computed_field
    @property
    def found(self) -> bool:
        return self.rank is not None


class BaselineReport(BaseModel):
    """The measured current state. This is the deliverable of lesson 1."""

    corpus_documents: int
    questions_asked: int
    seconds_per_document: float
    fallback_documents: int

    accuracy_at_1: float
    accuracy_at_3: float
    accuracy_at_5: float
    accuracy_lookup: float
    accuracy_concept: float

    p50_seconds: float
    p90_seconds: float
    mean_seconds: float
    fallback_rate: float

    @computed_field
    @property
    def p50_minutes(self) -> float:
        return round(self.p50_seconds / 60, 2)

    @computed_field
    @property
    def mean_minutes(self) -> float:
        return round(self.mean_seconds / 60, 2)


class SuccessCriterion(BaseModel):
    """One numeric, measured, arguable commitment."""

    name: str
    baseline: str
    target: str
    measured_by: str


class ScopingPack(BaseModel):
    """What you hand the customer at the end of week one."""

    customer: str
    stated_ask: str
    restated_problem: str
    success_criteria: list[SuccessCriterion]
    kill_criteria: list[str]
    out_of_scope: list[str] = Field(default_factory=list)
