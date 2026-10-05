"""Running the golden set and gating on the result.

The gate is the reason this exists. An eval you look at when you remember to is
a dashboard. An eval that fails the build is a specification.
"""
from __future__ import annotations

import json
import pathlib
import statistics
from typing import Any

from src.answerer import Answerer
from src.llm import LLMClient
from src.models import CaseResult, Document, EvalCase, EvalReport, Regression
from src.scoring import score

BASELINE_PATH = pathlib.Path("evals/baseline.json")
# How far a metric may fall before the build fails. Small enough to catch a real
# regression, wide enough that ordinary noise does not block a merge.
TOLERANCE = 0.02


def run_eval(
    cases: list[EvalCase],
    documents: list[Document],
    client: LLMClient,
    label: str,
    top_k: int = 5,
) -> tuple[EvalReport, list[CaseResult]]:
    """Answer every case and score it."""
    if not cases:
        raise ValueError("Cannot run an eval with no cases")
    answerer = Answerer(documents, client, top_k=top_k)
    results: list[CaseResult] = []

    for case in cases:
        completion, doc_ids = answerer.answer(case.question)
        results.append(
            CaseResult(
                case_id=case.case_id,
                kind=case.kind,
                answerable=case.answerable,
                retrieved=case.answer_doc_id in doc_ids,
                correct=score(case, completion.text),
                answer=completion.text,
                seconds=completion.seconds,
                prompt_tokens=completion.prompt_tokens,
                completion_tokens=completion.completion_tokens,
            )
        )

    def rate(rows: list[CaseResult], field: str = "correct") -> float:
        return round(sum(getattr(r, field) for r in rows) / len(rows), 4) if rows else 0.0

    answerable = [r for r in results if r.answerable]

    report = EvalReport(
        label=label,
        model=client.name,
        cases=len(results),
        lookup_cases=sum(1 for r in results if r.kind == "lookup"),
        concept_cases=sum(1 for r in results if r.kind == "concept"),
        answerable_cases=len(answerable),
        retrieval_hit_rate=rate(answerable, "retrieved"),
        accuracy=rate(results),
        accuracy_answerable=rate(answerable),
        accuracy_lookup=rate([r for r in results if r.kind == "lookup"]),
        accuracy_concept=rate([r for r in results if r.kind == "concept"]),
        mean_seconds=round(statistics.fmean(r.seconds for r in results), 3),
        total_completion_tokens=sum(r.completion_tokens for r in results),
    )
    return report, results


GATED_METRICS = ("accuracy", "accuracy_lookup", "accuracy_concept", "retrieval_hit_rate")


def compare_to_baseline(
    report: EvalReport, baseline: dict[str, Any], tolerance: float = TOLERANCE
) -> list[Regression]:
    """Return every gated metric that fell further than the tolerance allows."""
    regressions: list[Regression] = []
    for metric in GATED_METRICS:
        if metric not in baseline:
            continue
        before = float(baseline[metric])
        after = float(getattr(report, metric))
        if before - after > tolerance:
            regressions.append(
                Regression(metric=metric, baseline=before, current=after,
                           drop=round(before - after, 4))
            )
    return regressions


def load_baseline(path: pathlib.Path = BASELINE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def save_baseline(report: EvalReport, path: pathlib.Path = BASELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {m: float(getattr(report, m)) for m in GATED_METRICS}
    payload["model"] = report.model
    payload["cases"] = report.cases
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
