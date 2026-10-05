"""The scenarios are the known right answers, so they get checked too."""
from __future__ import annotations

import pytest

from src.guard import check
from src.policy import MERIDIAN
from src.scenarios import Kind, all_scenarios

SCENARIOS = all_scenarios()
GUARD_KINDS = {"out-of-scope-path", "deletion", "new-dependency",
               "too-many-files", "forbidden-content"}


class TestTheSetItself:
    def test_the_order_is_fixed_so_two_runs_print_the_same_table(self) -> None:
        assert [s.change.title for s in all_scenarios()] == [s.change.title for s in SCENARIOS]

    def test_every_title_is_different(self) -> None:
        titles = [s.change.title for s in SCENARIOS]
        assert len(set(titles)) == len(titles)

    def test_every_scenario_says_what_was_asked_for(self) -> None:
        assert all(s.change.asked_for for s in SCENARIOS)

    def test_there_is_one_scenario_per_class_the_guard_checks(self) -> None:
        expected = {s.expects for s in SCENARIOS if s.kind is Kind.MECHANICAL}
        assert expected == GUARD_KINDS

    def test_there_are_at_least_two_that_only_a_person_can_refuse(self) -> None:
        assert len([s for s in SCENARIOS if s.kind is Kind.SCOPE_CREEP]) >= 2


class TestTheLabelsAreHonest:
    @pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s.kind is Kind.MECHANICAL],
                             ids=lambda s: s.change.title)
    def test_a_mechanical_scenario_reports_the_class_it_claims(self, scenario) -> None:
        assert scenario.expects in check(scenario.change, MERIDIAN).kinds()

    @pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s.kind is Kind.SCOPE_CREEP],
                             ids=lambda s: s.change.title)
    def test_a_scope_creep_scenario_breaks_no_written_rule(self, scenario) -> None:
        """If one of these ever trips the guard, the scenario is mislabelled and
        the lesson's number is wrong."""
        result = check(scenario.change, MERIDIAN)
        assert result.allowed, f"expected clean, got {sorted(result.kinds())}"
        assert scenario.expects is None
        assert scenario.why

    @pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s.kind is Kind.IN_SCOPE],
                             ids=lambda s: s.change.title)
    def test_an_in_scope_scenario_is_allowed_and_needs_no_excuse(self, scenario) -> None:
        assert check(scenario.change, MERIDIAN).allowed
        assert scenario.why == ""
