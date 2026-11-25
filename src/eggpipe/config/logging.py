"""Single setup point for CLI logging."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from typing_extensions import override

from eggpipe.config.app_config import AppConfig

LOGGER_NAME = "eggpipe"
_FALLBACK_MESSAGE = "log serialization failed"
_OPTIONAL_FIELDS = ("run_id", "event", "duration_ms", "exception")
_STANDARD_FIELDS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None)))


def _timestamp(created: float) -> str:
    moment = datetime.fromtimestamp(created, tz=UTC)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def relative_text(value: object, *, base: Path) -> str:
    """Render path-bearing text relative to ``base`` for logs (ADR-0021)."""
    text = str(value)
    prefix = str(base)
    if not prefix:
        return text
    if text == prefix:
        return "."
    return text.replace(prefix + os.sep, "")


def display_path(path: Path, *, base: Path) -> str:
    """Relative POSIX path for logs; outside ``base`` it keeps a ``../`` form (ADR-0021)."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        pass
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:
        return path.name


def _fallback_record(record: logging.LogRecord) -> str:
    try:
        name = record.name
    except Exception:
        name = LOGGER_NAME
    timestamp = _timestamp(time.time())
    return (
        f'{{"ts":"{timestamp}","level":"error",'
        f'"logger":"{_escape(name)}","message":"{_FALLBACK_MESSAGE}"}}'
    )


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line (ADR-0021)."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        try:
            payload: dict[str, Any] = {
                "ts": _timestamp(record.created),
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
            }
            for key in _OPTIONAL_FIELDS:
                value = getattr(record, key, None)
                if value is not None:
                    payload[key] = value
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            extra = {
                key: value
                for key, value in vars(record).items()
                if key not in _STANDARD_FIELDS and key not in _OPTIONAL_FIELDS
            }
            if extra:
                payload["extra"] = extra
            return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
        except Exception:
            return _fallback_record(record)


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def setup_logging(config: AppConfig) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    level = (
        logging.DEBUG
        if config.verbose
        else getattr(logging, config.log_level.upper(), logging.INFO)
    )
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    if config.log_destination.startswith("file:"):
        path = Path(config.log_destination.removeprefix("file:"))
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(path, encoding="utf-8")
    elif config.log_destination == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.StreamHandler(sys.stderr)
    if config.log_mode == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(config.log_format))
    logger.addHandler(handler)
    return logger


__all__ = [
    "LOGGER_NAME",
    "JsonLogFormatter",
    "display_path",
    "get_logger",
    "relative_text",
    "setup_logging",
]
