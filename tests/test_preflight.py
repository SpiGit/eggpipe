"""Tests for the local preflight command list."""

from __future__ import annotations

import subprocess

import pytest
import tools.preflight as preflight
from tools.preflight import clean_env, commands


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


def test_clean_env_removes_git_hook_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/repo/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/repo")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = clean_env()
    assert "GIT_DIR" not in env
    assert "GIT_WORK_TREE" not in env
    assert env["PATH"] == "/usr/bin"


def test_main_passes_clean_env_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/repo/.git")

    def fake_which(name: str) -> str:
        return "/usr/bin/uv"

    monkeypatch.setattr(preflight.shutil, "which", fake_which)
    captured: list[dict[str, str]] = []

    def fake_run(
        command: list[str], *, check: bool, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        captured.append(env)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert preflight.main(["--fast"]) == 0
    assert len(captured) == 2
    assert all("GIT_DIR" not in env for env in captured)
