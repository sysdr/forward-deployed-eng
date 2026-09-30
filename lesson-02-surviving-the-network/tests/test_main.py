"""The commands a reader types."""
from __future__ import annotations

import sys


class TestCommandLine:
    def test_a_run_reports_what_happened(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--claims", "40", "--fail-rate", "0.3"])
        m.main()
        out = capsys.readouterr().out
        assert "documents kept" in out
        assert "of those, retries" in out
        assert "made it through" in out

    def test_without_retries_the_run_is_worse(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--claims", "40", "--fail-rate", "0.9", "--no-retry"])
        m.main()
        out = capsys.readouterr().out
        assert "no retries" in out
        assert "pages lost" in out

    def test_the_jitter_demo_prints_two_numbers(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--demo-jitter"])
        m.main()
        out = capsys.readouterr().out
        assert "without jitter" in out
        assert "with jitter" in out
