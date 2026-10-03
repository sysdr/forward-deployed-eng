"""The commands a reader types. The oracle path needs no model."""
from __future__ import annotations

import sys

import pytest


class TestCommandLine:
    def test_oracle_run_prints_the_split(self, monkeypatch, capsys) -> None:
        from src import main as m

        monkeypatch.setattr(sys, "argv", ["src.main", "--model", "oracle"])
        m.main()
        out = capsys.readouterr().out
        assert "answer in context" in out
        assert "retrieval" in out
        assert "the model's share" in out

    def test_save_baseline_writes_the_file(self, monkeypatch, tmp_path, capsys) -> None:
        from src import main as m

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "60", "--save-baseline"])
        m.main()
        assert (tmp_path / "evals" / "baseline.json").exists()
        assert "baseline written" in capsys.readouterr().out

    def test_gate_passes_against_a_fresh_baseline(self, monkeypatch, tmp_path, capsys) -> None:
        from src import main as m

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "60", "--save-baseline"])
        m.main()
        capsys.readouterr()
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "60", "--gate"])
        m.main()
        assert "no regression" in capsys.readouterr().out

    def test_gate_without_a_baseline_exits_one(self, monkeypatch, tmp_path) -> None:
        from src import main as m

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "40", "--gate"])
        with pytest.raises(SystemExit) as exc:
            m.main()
        assert exc.value.code == 1

    def test_degrading_retrieval_trips_the_gate(self, monkeypatch, tmp_path, capsys) -> None:
        """The criterion a reader is told to try. It has to actually work."""
        from src import main as m

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "60", "--save-baseline"])
        m.main()
        capsys.readouterr()
        monkeypatch.setattr(
            sys, "argv",
            ["src.main", "--model", "oracle", "--claims", "60", "--top-k", "1", "--gate"],
        )
        with pytest.raises(SystemExit) as exc:
            m.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "REGRESSION" in out
        assert "retrieval_hit_rate" in out

    def test_gate_fails_when_the_baseline_is_better(self, monkeypatch, tmp_path, capsys) -> None:
        """The build must break when quality drops. This is the whole feature."""
        from src import main as m

        monkeypatch.chdir(tmp_path)
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "baseline.json").write_text(
            '{"accuracy": 0.99, "accuracy_lookup": 0.99,'
            ' "accuracy_concept": 0.99, "retrieval_hit_rate": 0.99}'
        )
        monkeypatch.setattr(sys, "argv",
                            ["src.main", "--model", "oracle", "--claims", "60", "--gate"])
        with pytest.raises(SystemExit) as exc:
            m.main()
        assert exc.value.code == 1
        assert "REGRESSION" in capsys.readouterr().out
