"""Tests for provenance."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from eggpipe import git_provenance

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _clear_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove GIT_* variables inherited from a pre-push hook."""
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key, raising=False)


def test_git_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_git_env(monkeypatch)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    path = tmp_path / "model.yaml"
    path.write_text("format: entity-model\nversion: '1.0'\nmodel: {}\n", encoding="utf-8")
    subprocess.run(["git", "add", "model.yaml"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "initial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    provenance = git_provenance(path)
    assert provenance is not None
    assert provenance.commit is not None
    assert isinstance(provenance.date, datetime)


def test_git_provenance_without_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_git_env(monkeypatch)
    path = tmp_path / "model.yaml"
    path.write_text("", encoding="utf-8")
    assert git_provenance(path) is None
