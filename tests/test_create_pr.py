"""Tests for the pull request helper."""

from __future__ import annotations

from tools.create_pr import build_body, default_title, repo_from_remote


def test_repo_from_remote() -> None:
    assert repo_from_remote("git@github-eggpipe:SpiGit/eggpipe.git") == "SpiGit/eggpipe"
    assert repo_from_remote("https://github.com/SpiGit/eggpipe.git") == "SpiGit/eggpipe"
    assert repo_from_remote("https://github.com/SpiGit/eggpipe") == "SpiGit/eggpipe"


def test_build_body() -> None:
    assert build_body(["feat: add thing", "test: cover thing"]) == (
        "## Что изменено\n\n- feat: add thing\n- test: cover thing\n"
    )


def test_default_title() -> None:
    assert default_title(["feat: add thing"], "chore/example") == "feat: add thing"
    assert default_title([], "chore/example") == "chore/example"
