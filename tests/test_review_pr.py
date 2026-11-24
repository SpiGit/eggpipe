"""Tests for the pull request review helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import tools.create_pr as create_pr
import tools.review_pr as review_pr


def test_find_open_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    def found(
        method: str,
        path: str,
        token: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        return [{"number": 7}]

    monkeypatch.setattr(create_pr, "_api", found)
    assert create_pr.find_open_pr("SpiGit/eggpipe", "feat/x", "token") == 7

    def missing(
        method: str,
        path: str,
        token: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        empty: list[dict[str, object]] = []
        return empty

    monkeypatch.setattr(create_pr, "_api", missing)
    assert create_pr.find_open_pr("SpiGit/eggpipe", "feat/x", "token") is None


def test_review_defaults_to_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict[str, object]] = []

    def fake_api(
        method: str,
        path: str,
        token: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        assert method == "POST"
        assert path == "/repos/SpiGit/eggpipe/pulls/7/reviews"
        assert payload is not None
        payloads.append(payload)
        return {"id": 1, "html_url": "https://example.test/review"}

    def fake_remote(remote: str) -> str:
        return "SpiGit/eggpipe"

    def fake_git(*args: str) -> str:
        return "main"

    monkeypatch.setattr(review_pr, "repo_from_remote", fake_remote)
    monkeypatch.setattr(review_pr, "_run_git", fake_git)
    monkeypatch.setattr(review_pr, "_token", lambda: "token")
    monkeypatch.setattr(review_pr, "_api", fake_api)

    assert review_pr.main(["--pr", "7", "--body", "ok"]) == 0
    assert payloads[0]["event"] == "COMMENT"


def test_review_reads_body_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payloads: list[dict[str, object]] = []

    def fake_api(
        method: str,
        path: str,
        token: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        assert payload is not None
        payloads.append(payload)
        return {"id": 2, "html_url": "https://example.test/review"}

    def fake_remote(remote: str) -> str:
        return "SpiGit/eggpipe"

    def fake_git(*args: str) -> str:
        return "main"

    monkeypatch.setattr(review_pr, "repo_from_remote", fake_remote)
    monkeypatch.setattr(review_pr, "_run_git", fake_git)
    monkeypatch.setattr(review_pr, "_token", lambda: "token")
    monkeypatch.setattr(review_pr, "_api", fake_api)

    body_file = tmp_path / "review.md"
    body_file.write_text("VERDICT: APPROVE\n", encoding="utf-8")
    assert review_pr.main(["--pr", "7", "--body-file", str(body_file)]) == 0
    assert payloads[0]["body"] == "VERDICT: APPROVE\n"


def test_review_rejects_body_and_body_file(tmp_path: Path) -> None:
    body_file = tmp_path / "review.md"
    body_file.write_text("ok", encoding="utf-8")
    with pytest.raises(SystemExit):
        review_pr.main(["--pr", "7", "--body", "ok", "--body-file", str(body_file)])


def test_review_requires_body() -> None:
    with pytest.raises(SystemExit):
        review_pr.main(["--body", "  "])


def test_script_mode_imports_create_pr() -> None:
    result = subprocess.run(
        [sys.executable, "tools/review_pr.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Submit a pull request review" in result.stdout
