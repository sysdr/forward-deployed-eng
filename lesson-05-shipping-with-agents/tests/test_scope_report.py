"""The scored table a reader gets from `make run`."""
from __future__ import annotations

import sys

from src.guard import check
from src.main import guard_command, is_right, render, score, widen
from src.policy import MERIDIAN
from src.scenarios import Kind, all_scenarios

ROWS = score(MERIDIAN, all_scenarios())


class TestScoring:
    def test_a_mechanical_scenario_is_right_only_when_its_own_class_is_reported(self) -> None:
        scenario = next(s for s in all_scenarios() if s.expects == "deletion")
        assert is_right(scenario, check(scenario.change, MERIDIAN))
        mislabelled = scenario.model_copy(update={"expects": "forbidden-content"})
        assert not is_right(mislabelled, check(scenario.change, MERIDIAN))

    def test_every_mechanical_scenario_is_caught(self) -> None:
        assert all(ok for s, _, ok in ROWS if s.kind is Kind.MECHANICAL)

    def test_no_scope_creep_scenario_is_caught(self) -> None:
        """The measurement the lesson reports. Not an aspiration."""
        assert not any(ok for s, _, ok in ROWS if s.kind is Kind.SCOPE_CREEP)

    def test_the_in_scope_change_is_let_through(self) -> None:
        assert all(ok for s, _, ok in ROWS if s.kind is Kind.IN_SCOPE)


class TestTheTable:
    def test_it_has_a_row_for_every_scenario(self) -> None:
        text = render(ROWS)
        for scenario, _, _ in ROWS:
            assert scenario.change.title in text

    def test_it_prints_the_two_counts_that_matter(self) -> None:
        text = render(ROWS)
        assert "mechanical violations caught : 6 of 6" in text
        assert "doing more than was asked    : 0 of 3" in text

    def test_it_names_what_got_through_and_why(self) -> None:
        text = render(ROWS)
        assert "Got through, having satisfied every written rule:" in text
        assert "Raise the document fetch timeout from 2s to 10s." in text

    def test_a_clean_run_prints_no_leftover_section(self) -> None:
        clean = [(s, r, ok) for s, r, ok in ROWS if s.kind is Kind.IN_SCOPE]
        assert "Got through" not in render(clean)


class TestWideningThePolicy:
    def test_one_added_glob_changes_the_score(self) -> None:
        wider = widen(MERIDIAN, "services/search-gateway/**")
        before = sum(1 for _, _, ok in ROWS if ok)
        after = sum(1 for _, _, ok in score(wider, all_scenarios()) if ok)
        assert after == before - 1

    def test_it_does_not_unblock_a_never_touch_path(self) -> None:
        wider = widen(MERIDIAN, "infra/**")
        row = next(r for r in score(wider, all_scenarios())
                   if r[0].change.title.startswith("Give the assistant more memory"))
        assert "out-of-scope-path" in row[1].kinds()

    def test_nothing_else_about_the_policy_moved(self) -> None:
        wider = widen(MERIDIAN, "services/search-gateway/**")
        assert wider.never_touch == MERIDIAN.never_touch
        assert wider.max_files_per_change == MERIDIAN.max_files_per_change
        assert MERIDIAN.may_edit == ["services/claims-assistant/**",
                                     "docs/claims-assistant/**",
                                     "tests/claims_assistant/**"]


class TestTheCommand:
    def test_it_prints_the_policy_then_the_table(self, capsys) -> None:
        guard_command()
        out = capsys.readouterr().out
        assert "Policy: Meridian Mutual claims assistant" in out
        assert "overall" in out

    def test_the_allow_flag_is_reported_in_the_header(self, capsys) -> None:
        guard_command(allow="services/search-gateway/**")
        assert "widened by  may_edit += 'services/search-gateway/**'" in capsys.readouterr().out

    def test_it_is_what_you_get_with_no_arguments(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main"])
        m.main()
        assert "mechanical violations caught" in capsys.readouterr().out
