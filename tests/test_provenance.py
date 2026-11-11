"""Тесты provenance."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from metadata_generator import git_provenance

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git не установлен")


def test_git_provenance(tmp_path: Path) -> None:
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


def test_git_provenance_without_repo(tmp_path: Path) -> None:
    path = tmp_path / "model.yaml"
    path.write_text("", encoding="utf-8")
    assert git_provenance(path) is None
