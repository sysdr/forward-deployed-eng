"""Logs you can search at three in the morning.

Two ideas, and they only work together.

One line of JSON per event, so a log tool can filter on a field instead of you
reading with your eyes. And one identifier shared by every line from the same run,
so you can pull that run's whole story out of a file holding fifty other runs.

`print()` gives you neither.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_run_id: ContextVar[str] = ContextVar("run_id", default="")

# Attributes the logging module puts on every record. Anything not in here was
# added by the caller and belongs in the output.
_BUILTIN = frozenset(
    """args asctime created exc_info exc_text filename funcName levelname levelno
    lineno module msecs message msg name pathname process processName relativeCreated
    stack_info thread threadName taskName""".split()
)


def new_run_id() -> str:
    """Start a new run and return its identifier."""
    value = str(uuid.uuid4())
    _run_id.set(value)
    return value


def current_run_id() -> str:
    return _run_id.get()


class JsonFormatter(logging.Formatter):
    """One event, one line, every field searchable."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
            "run_id": current_run_id(),
            "where": f"{record.module}.{record.funcName}:{record.lineno}",
        }
        for key, value in record.__dict__.items():
            if key not in _BUILTIN and not key.startswith("_"):
                payload.setdefault(key, value)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """A logger that writes JSON to stdout. Safe to call repeatedly."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        # Without this, every line prints twice once a second module asks for a
        # logger, and you will not work out why for an hour.
        logger.propagate = False
    return logger
