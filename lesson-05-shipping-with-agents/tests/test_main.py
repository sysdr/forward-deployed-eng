"""The commands a reader types. The oracle path needs no model."""
from __future__ import annotations

import sys


class TestBudgetCommand:
    def test_it_prices_the_run_two_ways(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--budget", "--model", "oracle"])
        m.main()
        out = capsys.readouterr().out
        assert "local, on the laptop you already have" in out
        assert "a hosted API at illustrative rates" in out

    def test_it_separates_asked_from_answered(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--budget", "--model", "oracle"])
        m.main()
        out = capsys.readouterr().out
        assert "per question asked" in out
        assert "per question answered" in out
        assert "what they are buying" in out

    def test_it_shows_what_makes_the_bill_grow(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--budget", "--model", "oracle"])
        m.main()
        out = capsys.readouterr().out
        assert "What makes the hosted bill grow" in out
        assert "an agent that takes 8 steps" in out

    def test_it_states_when_the_prices_were_checked(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--budget", "--model", "oracle"])
        m.main()
        assert "rates checked" in capsys.readouterr().out


class TestLoadCommand:
    def test_it_reports_one_row_per_concurrency_level(self, capsys) -> None:
        """Runs against the oracle, so it measures the harness rather than a model."""
        from src import main as m

        m.load_command("oracle", concurrencies=(1, 2))
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
        header = next(i for i, ln in enumerate(lines) if "p95" in ln)
        rows = lines[header + 1 :]
        assert len(rows) == 2
        assert rows[0].split()[0] == "1"
        assert rows[1].split()[0] == "2"


class TestPrintedFiguresReproduce:
    def test_the_printed_per_question_figure_gives_the_printed_monthly(self, capsys) -> None:
        """Print fewer decimals than you computed with and a CFO's calculator
        disagrees with your slide. That argument is not winnable."""
        from src.budget import WORKING_DAYS_PER_MONTH, build_budget, price_run
        from src.models import Usage
        from src.pricing import HOSTED, LAPTOP

        usage = Usage(calls=42, prompt_tokens=17_873, completion_tokens=534,
                      cached_prefix_tokens=2_184, total_seconds=60.0,
                      p50_seconds=1.23, p95_seconds=4.61)
        cost = price_run("hosted", usage, HOSTED, LAPTOP)
        b = build_budget("hosted", usage, cost, 42, 22)
        printed = float(f"{b.cost_per_question:.6f}")
        volume = b.questions_per_adjuster_per_day * b.adjusters * WORKING_DAYS_PER_MONTH
        assert round(printed * volume, 2) == b.cost_per_month
