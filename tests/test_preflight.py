"""Tests for the local preflight command list."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import tools.preflight as preflight
from tools.preflight import clean_env, commands, is_unchanged, tree_hash


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


def _which(name: str) -> str:
    return "/usr/bin/uv"


def _fixed_hash(root: Path) -> str:
    return "abc"


def _stamp_factory(stamp: Path) -> Callable[[Path], Path]:
    def path(root: Path) -> Path:
        return stamp

    return path


def _patch_uv(monkeypatch: pytest.MonkeyPatch, captured: list[list[str]]) -> None:
    monkeypatch.setattr(preflight.shutil, "which", _which)

    def fake_run(
        command: list[str], *, check: bool, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        captured.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)


def test_tree_hash_changes_with_content(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    file = tmp_path / "src" / "module.py"
    file.write_text("a = 1\n", encoding="utf-8")
    first = tree_hash(tmp_path)
    file.write_text("a = 2\n", encoding="utf-8")
    assert tree_hash(tmp_path) != first


def test_tree_hash_ignores_skipped_parts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("a = 1\n", encoding="utf-8")
    baseline = tree_hash(tmp_path)
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "module.pyc").write_bytes(b"junk")
    assert tree_hash(tmp_path) == baseline


def test_is_unchanged(tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    assert is_unchanged(stamp, "abc") is False
    stamp.write_text("abc\n", encoding="utf-8")
    assert is_unchanged(stamp, "abc") is True
    assert is_unchanged(stamp, "other") is False


def test_stamp_skips_heavy_checks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    stamp.write_text("abc\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp"]) == 0
    assert len(captured) == 2
    assert captured[0][:3] == ["uv", "run", "ruff"]
    assert is_unchanged(stamp, "abc") is True


def test_stamp_writes_after_full_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp"]) == 0
    assert len(captured) == 8
    assert is_unchanged(stamp, "abc") is True


def test_stamp_removed_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    stamp.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    monkeypatch.setattr(preflight.shutil, "which", _which)

    def failing_run(
        command: list[str], *, check: bool, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(preflight.subprocess, "run", failing_run)

    assert preflight.main(["--stamp"]) == 1
    assert not stamp.exists()


def test_stamp_hash_mismatch_runs_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stamp = tmp_path / "stamp"
    stamp.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp"]) == 0
    assert len(captured) == 8
    assert is_unchanged(stamp, "abc") is True


def test_stamp_with_fast_does_not_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp", "--fast"]) == 0
    assert len(captured) == 2
    assert not stamp.exists()


def test_stamp_unavailable_does_not_fail_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory\n", encoding="utf-8")
    missing = blocker / "nested" / "stamp"
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(missing))
    monkeypatch.setattr(preflight, "tree_hash", _fixed_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp"]) == 0


def test_tree_hash_covers_root_documents(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("first\n", encoding="utf-8")
    baseline = tree_hash(tmp_path)
    (tmp_path / "README.md").write_text("second\n", encoding="utf-8")
    assert tree_hash(tmp_path) != baseline


def test_unreadable_input_disables_stamp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "stamp_path", _stamp_factory(stamp))

    def empty_hash(root: Path) -> str:
        return ""

    monkeypatch.setattr(preflight, "tree_hash", empty_hash)
    captured: list[list[str]] = []
    _patch_uv(monkeypatch, captured)

    assert preflight.main(["--stamp"]) == 0
    assert len(captured) == 8
    assert not stamp.exists()
