"""Logs are only useful if a machine can filter them and a human can follow one run."""
from __future__ import annotations

import json
import logging

from src.obs import current_run_id, get_logger, new_run_id


def emit(logger: logging.Logger, capsys, message: str, **fields: object) -> dict:
    logger.info(message, extra=fields)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    return json.loads(line)


class TestJsonOutput:
    def test_every_line_is_one_json_object(self, capsys) -> None:
        log = get_logger("t.one")
        record = emit(log, capsys, "page fetched", page=3, kept=50)
        assert record["event"] == "page fetched"
        assert record["level"] == "INFO"

    def test_caller_fields_are_searchable_at_the_top_level(self, capsys) -> None:
        """Not buried in the message string, where no log tool can filter them."""
        log = get_logger("t.two")
        record = emit(log, capsys, "page fetched", page=3, kept=50)
        assert record["page"] == 3
        assert record["kept"] == 50

    def test_it_says_where_the_line_came_from(self, capsys) -> None:
        log = get_logger("t.three")
        assert "test_obs" in emit(log, capsys, "hello")["where"]

    def test_an_exception_is_included(self, capsys) -> None:
        log = get_logger("t.four")
        try:
            raise ValueError("boom")
        except ValueError:
            log.exception("it broke")
        record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "ValueError: boom" in record["error"]


class TestRunId:
    def test_every_line_in_a_run_shares_one_id(self, capsys) -> None:
        log = get_logger("t.five")
        run = new_run_id()
        a = emit(log, capsys, "first")
        b = emit(log, capsys, "second")
        assert a["run_id"] == b["run_id"] == run

    def test_a_new_run_gets_a_new_id(self) -> None:
        first = new_run_id()
        assert new_run_id() != first

    def test_the_current_id_is_readable(self) -> None:
        run = new_run_id()
        assert current_run_id() == run


class TestLoggerSetup:
    def test_asking_twice_does_not_double_every_line(self, capsys) -> None:
        """The bug that makes people think their loop ran twice."""
        get_logger("t.six")
        log = get_logger("t.six")
        log.info("once")
        assert len(capsys.readouterr().out.strip().splitlines()) == 1

    def test_it_does_not_leak_into_the_root_logger(self) -> None:
        assert get_logger("t.seven").propagate is False

    def test_builtin_record_fields_are_not_copied_out(self, capsys) -> None:
        log = get_logger("t.eight")
        record = emit(log, capsys, "hello")
        for noisy in ("msg", "args", "levelno", "pathname", "processName"):
            assert noisy not in record

    def test_unserialisable_values_do_not_crash_the_logger(self, capsys) -> None:
        log = get_logger("t.nine")
        record = emit(log, capsys, "odd", thing=object())
        assert "object object" in record["thing"]
