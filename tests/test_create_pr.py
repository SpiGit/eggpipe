"""Tests for the pull request helper."""

from __future__ import annotations

from tools.create_pr import (
    MAX_PR_LINES,
    DiffSize,
    build_body,
    default_title,
    is_generated,
    parse_numstat,
    repo_from_remote,
    size_warning,
)


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


def test_is_generated() -> None:
    assert is_generated("docs/ai/llms.txt")
    assert is_generated("engineering/requirements/v2.3.md")
    assert is_generated("uv.lock")
    assert not is_generated("src/eggpipe/engine/engine.py")
    assert not is_generated("engineering/requirements/index.md")


def test_parse_numstat_excludes_generated() -> None:
    size = parse_numstat(
        "10\t2\tsrc/eggpipe/engine.py\n"
        "5\t0\tdocs/ai/llms.txt\n"
        "-\t-\tuv.lock\n"
        "3\t1\tengineering/requirements/v2.3.md\n"
    )
    assert size.lines == 12
    assert size.files == 1
    assert size.generated_lines == 9
    assert size.generated_files == 3
    assert size.too_large is False


def test_size_warning() -> None:
    assert size_warning(DiffSize(lines=10, files=1)) is None
    warning = size_warning(DiffSize(lines=MAX_PR_LINES + 1, files=1))
    assert warning is not None
    assert "Split into stacked PRs" in warning
    assert "hand-written lines" in warning
    assert size_warning(DiffSize(lines=1, files=16)) is not None
