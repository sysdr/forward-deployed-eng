"""The eval runner and the gate. The gate is what makes this a specification."""
from __future__ import annotations

import json

import pytest

from src.evaluate import (
    compare_to_baseline,
    load_baseline,
    run_eval,
    save_baseline,
)
from src.llm import ScriptedLLM


class TestRunEval:
    def test_no_cases_is_rejected(self, documents) -> None:
        with pytest.raises(ValueError, match="no cases"):
            run_eval([], documents, ScriptedLLM(), label="x")

    def test_oracle_accuracy_equals_its_retrieval_rate(self, cases, documents, oracle) -> None:
        """On answerable cases the oracle is right exactly when retrieval put the
        answer in front of it, so these two numbers match by construction. If they
        ever diverge, the scorer and the golden set disagree.

        Refusal cases are excluded: they are correct *because* nothing was
        retrieved, and counting them here made headroom go negative.
        """
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        assert report.accuracy_answerable == report.retrieval_hit_rate
        assert report.headroom == 0.0

    def test_refusals_are_excluded_from_the_retrieval_rate(
        self, cases, documents, oracle
    ) -> None:
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        assert report.answerable_cases == report.cases - 1
        assert report.accuracy > report.accuracy_answerable

    def test_a_model_that_always_refuses_scores_near_zero(self, cases, documents) -> None:
        llm = ScriptedLLM(default="The context does not contain the answer.")
        report, _ = run_eval(cases, documents, llm, label="refuser")
        # It is right only on the case where refusing is the correct answer.
        assert report.accuracy < 0.05
        assert report.retrieval_hit_rate > 0.4

    def test_headroom_exposes_a_model_failure(self, cases, documents) -> None:
        """Retrieval succeeds, the model still gets it wrong. That gap tells you
        to change model rather than change retrieval."""
        llm = ScriptedLLM(default="Banana.")
        report, _ = run_eval(cases, documents, llm, label="useless")
        assert report.accuracy == 0.0
        assert report.headroom == report.retrieval_hit_rate

    def test_subset_counts_are_reported(self, cases, documents, oracle) -> None:
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        assert report.lookup_cases + report.concept_cases == report.cases


class TestGate:
    BASE = {"accuracy": 0.60, "accuracy_lookup": 1.0,
            "accuracy_concept": 0.20, "retrieval_hit_rate": 0.60}

    def _report(self, cases, documents, oracle):
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        return report

    def test_no_regression_when_metrics_hold(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        generous = {k: 0.0 for k in self.BASE}
        assert compare_to_baseline(report, generous) == []

    def test_a_real_drop_is_caught(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        strict = {k: 1.0 for k in self.BASE}
        found = {r.metric for r in compare_to_baseline(report, strict)}
        assert "accuracy" in found

    def test_a_drop_inside_tolerance_is_allowed(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        baseline = {"accuracy": report.accuracy + 0.01}
        assert compare_to_baseline(report, baseline) == []

    def test_a_drop_outside_tolerance_is_not(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        baseline = {"accuracy": report.accuracy + 0.05}
        regressions = compare_to_baseline(report, baseline)
        assert len(regressions) == 1
        assert regressions[0].drop == pytest.approx(0.05, abs=1e-6)

    def test_metrics_absent_from_the_baseline_are_skipped(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        assert compare_to_baseline(report, {}) == []

    def test_an_improvement_never_fails_the_build(self, cases, documents, oracle) -> None:
        report = self._report(cases, documents, oracle)
        assert compare_to_baseline(report, {"accuracy": 0.0}) == []


class TestBaselineFile:
    def test_round_trips(self, cases, documents, oracle, tmp_path) -> None:
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        path = tmp_path / "evals" / "baseline.json"
        save_baseline(report, path)
        loaded = load_baseline(path)
        assert loaded is not None
        assert loaded["accuracy"] == report.accuracy
        assert str(loaded["model"]) == "oracle"

    def test_missing_file_returns_none(self, tmp_path) -> None:
        assert load_baseline(tmp_path / "nope.json") is None

    def test_written_file_is_readable_json(self, cases, documents, oracle, tmp_path) -> None:
        report, _ = run_eval(cases, documents, oracle, label="oracle")
        path = tmp_path / "b.json"
        save_baseline(report, path)
        assert json.loads(path.read_text())["cases"] == report.cases
