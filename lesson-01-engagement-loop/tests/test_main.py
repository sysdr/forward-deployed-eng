"""End to end: the command a reader actually types has to work."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys


class TestCommandLine:
    def test_module_runs_and_reports_a_baseline(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--claims", "60"],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "Scoping Pack" in result.stdout
        assert "median time to answer" in result.stdout

    def test_write_flag_produces_the_pack(self, tmp_path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--claims", "40", "--write"],
            capture_output=True, text=True, cwd=tmp_path, timeout=120,
            env={**os.environ, "PYTHONPATH": str(pathlib.Path.cwd())},
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "scoping-pack.md").exists()


class TestEntryPointInProcess:
    """The subprocess tests prove the command works. These prove the code inside it does."""

    def test_main_prints_report_and_pack(self, monkeypatch, capsys) -> None:
        from src import main as main_module

        monkeypatch.setattr(sys, "argv", ["src.main", "--claims", "40"])
        main_module.main()
        out = capsys.readouterr().out
        assert "Corpus:" in out
        assert "answer in top 5" in out
        assert "# Scoping Pack — Meridian Mutual" in out
        assert "Kill criteria" in out

    def test_main_write_flag_writes_the_file(self, monkeypatch, tmp_path, capsys) -> None:
        from src import main as main_module

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["src.main", "--claims", "40", "--write"])
        main_module.main()
        written = tmp_path / "scoping-pack.md"
        assert written.exists()
        assert "Success criteria" in written.read_text(encoding="utf-8")
        assert "Wrote" in capsys.readouterr().out

    def test_smaller_corpus_changes_the_baseline(self, monkeypatch, capsys) -> None:
        """Guards against the report being accidentally hard-coded."""
        from src import main as main_module

        monkeypatch.setattr(sys, "argv", ["src.main", "--claims", "40"])
        main_module.main()
        small = capsys.readouterr().out
        monkeypatch.setattr(sys, "argv", ["src.main", "--claims", "200"])
        main_module.main()
        assert small != capsys.readouterr().out
