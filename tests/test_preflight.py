"""Tests for the local preflight command list."""

from __future__ import annotations

from tools.preflight import commands


def test_fast_commands() -> None:
    result = commands(fast=True)
    assert len(result) == 2
    assert result[0][:3] == ["uv", "run", "ruff"]
    assert "format" in result[1]


def test_full_commands() -> None:
    result = commands(fast=False)
    joined = [" ".join(command) for command in result]
    assert any("pyrefly" in item for item in joined)
    assert any("pytest" in item for item in joined)
    assert any("check_docs.py" in item for item in joined)
    assert any("mkdocs" in item for item in joined)
    assert any("check_wheel.py" in item for item in joined)
