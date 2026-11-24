"""Tests for structured logging and log configuration (ADR-0021)."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from eggpipe.config.app_config import AppConfig
from eggpipe.config.logging import JsonLogFormatter, setup_logging


def make_record() -> logging.LogRecord:
    return logging.LogRecord(
        "eggpipe.engine", logging.INFO, __file__, 1, "cache %s", ("pruned",), None
    )


def test_json_formatter_emits_required_and_optional_fields() -> None:
    record = make_record()
    record.run_id = "run-1"
    record.event = "cache.prune"
    record.duration_ms = 3
    record.entries = 8

    data = json.loads(JsonLogFormatter().format(record))

    assert data["level"] == "info"
    assert data["logger"] == "eggpipe.engine"
    assert data["message"] == "cache pruned"
    assert data["ts"].endswith("Z") and "." in data["ts"]
    assert data["run_id"] == "run-1"
    assert data["event"] == "cache.prune"
    assert data["duration_ms"] == 3
    assert data["extra"] == {"entries": 8}


def test_json_formatter_accepts_exception_attribute() -> None:
    record = make_record()
    record.exception = "boom"

    data = json.loads(JsonLogFormatter().format(record))

    assert data["exception"] == "boom"
    assert "exception" not in data.get("extra", {})


def test_json_formatter_includes_exception() -> None:
    record = make_record()
    try:
        raise ZeroDivisionError("boom")
    except ZeroDivisionError:
        record.exc_info = sys.exc_info()

    data = json.loads(JsonLogFormatter().format(record))

    assert "ZeroDivisionError" in data["exception"]


def test_json_formatter_serializes_non_primitive_extra() -> None:
    record = make_record()
    record.payload = object()

    data = json.loads(JsonLogFormatter().format(record))

    assert isinstance(data["extra"]["payload"], str)


def test_json_formatter_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*args: object, **kwargs: object) -> str:
        raise ValueError("boom")

    monkeypatch.setattr("eggpipe.config.logging.json.dumps", broken)

    data = json.loads(JsonLogFormatter().format(make_record()))

    assert data["level"] == "error"
    assert data["logger"] == "eggpipe.engine"
    assert data["message"] == "log serialization failed"
    assert data["ts"].endswith("Z")


def test_setup_logging_selects_json_formatter() -> None:
    logger = setup_logging(AppConfig(_env_file=None, log_mode="json"))
    try:
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JsonLogFormatter)
    finally:
        logger.handlers.clear()


def test_setup_logging_keeps_text_formatter() -> None:
    logger = setup_logging(AppConfig(_env_file=None))
    try:
        handler = logger.handlers[0]
        assert type(handler.formatter) is logging.Formatter
    finally:
        logger.handlers.clear()


def test_log_mode_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGGPIPE_LOG_MODE", "json")
    assert AppConfig(_env_file=None).log_mode == "json"


def test_log_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGGPIPE_LOG_MODE", "xml")
    with pytest.raises(ValueError):
        AppConfig(_env_file=None)
