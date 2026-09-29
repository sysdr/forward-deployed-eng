"""The scoping pack must trace every number to the measurement."""
from __future__ import annotations

from src.scope import build_scoping_pack, render


class TestScopingPack:
    def test_every_criterion_has_a_measurement_method(self, measured) -> None:
        report, _ = measured
        pack = build_scoping_pack(report)
        assert pack.success_criteria
        for c in pack.success_criteria:
            assert c.measured_by.strip()
            assert c.baseline.strip()
            assert c.target.strip()

    def test_baselines_come_from_the_report_not_a_constant(self, measured) -> None:
        report, _ = measured
        pack = build_scoping_pack(report)
        top5 = next(c for c in pack.success_criteria if c.name == "Answer found in top 5")
        assert top5.baseline == f"{report.accuracy_at_5:.0%}"

    def test_kill_criteria_are_present_and_specific(self, measured) -> None:
        report, _ = measured
        pack = build_scoping_pack(report)
        assert len(pack.kill_criteria) >= 3
        assert any("%" in k or "half" in k for k in pack.kill_criteria)

    def test_rendered_pack_contains_the_measured_numbers(self, measured) -> None:
        report, _ = measured
        markdown = render(build_scoping_pack(report), report)
        assert f"{report.accuracy_at_5:.0%}" in markdown
        assert str(report.corpus_documents) in markdown
        assert "Kill criteria" in markdown
