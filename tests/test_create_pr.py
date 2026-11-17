"""Tests for the pull request helper."""

from __future__ import annotations

import pytest
import tools.create_pr as create_pr
from tools.create_pr import (
    MAX_PR_FILES,
    MAX_PR_LINES,
    SIZE_BLOCK_END,
    SIZE_BLOCK_START,
    DiffSize,
    build_body,
    default_title,
    is_generated,
    main,
    parse_numstat,
    preserve_size_exception,
    repo_from_remote,
    size_block,
    size_warning,
    upsert_size_block,
    with_size_exception,
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


def _numstat(*tokens: str) -> str:
    """Render numstat tokens the way ``git diff --numstat -z`` separates them.

    A plain entry is one token such as ``"10\t2\tsrc/a.py"``. A rename uses three tokens:
    an entry with an empty path (``"1\t1\t"``), the source path and the destination path.
    """
    return "".join(f"{token}\0" for token in tokens)


def test_parse_numstat_excludes_generated() -> None:
    size = parse_numstat(
        _numstat(
            "10\t2\tsrc/eggpipe/engine.py",
            "5\t0\tdocs/ai/llms.txt",
            "-\t-\tuv.lock",
            "3\t1\tengineering/requirements/v2.3.md",
        )
    )
    assert size.lines == 12
    assert size.files == 1
    assert size.generated_lines == 9
    assert size.generated_files == 3
    assert size.too_large is False


def test_parse_numstat_uses_rename_destination() -> None:
    size = parse_numstat(
        _numstat(
            "1\t1\t",
            "src/old.py",
            "src/new.py",
            "2\t0\t",
            "src/old.txt",
            "docs/ai/llms.txt",
        )
    )
    assert size.lines == 2
    assert size.files == 1
    assert size.generated_lines == 2
    assert size.generated_files == 1


def test_parse_numstat_keeps_paths_verbatim() -> None:
    size = parse_numstat(_numstat("4\t0\tdocs/ai/weird\tname.txt", '2\t1\tsrc/quo"te.py'))
    assert size.lines == 3
    assert size.files == 1
    assert size.generated_lines == 4
    assert size.generated_files == 1


def test_parse_numstat_rename_with_spaces_and_quotes() -> None:
    size = parse_numstat(_numstat("1\t0\t", 'src/old "file".py', 'src/new "file".py'))
    assert size.lines == 1
    assert size.files == 1
    assert size.generated_lines == 0
    assert size.generated_files == 0


def test_size_warning() -> None:
    assert size_warning(DiffSize(lines=10, files=1)) is None
    assert size_warning(DiffSize(lines=MAX_PR_LINES, files=MAX_PR_FILES)) is None
    warning = size_warning(DiffSize(lines=MAX_PR_LINES + 1, files=1))
    assert warning is not None
    assert "Split into stacked PRs" in warning
    assert "hand-written lines" in warning
    assert size_warning(DiffSize(lines=1, files=MAX_PR_FILES + 1)) is not None
    assert DiffSize(lines=MAX_PR_LINES, files=MAX_PR_FILES).too_large is False
    assert DiffSize(lines=1, files=MAX_PR_FILES + 1).too_large is True


def test_with_size_exception() -> None:
    assert with_size_exception("body\n", None) == "body\n"
    body = with_size_exception("body\n", "large spec update")
    assert body.endswith("## Size exception\n\nlarge spec update\n")
    assert with_size_exception(body, "another reason") == body


def test_preserve_size_exception() -> None:
    body = "## Что изменено\n\n- feat: add thing\n"
    assert preserve_size_exception(body, "") == body
    assert preserve_size_exception(body, "## Что изменено\n\n- old\n") == body

    previous = f"{body}\n## Size exception\n\nlarge spec update\n"
    assert preserve_size_exception(body, previous).endswith(
        "## Size exception\n\nlarge spec update\n"
    )
    assert preserve_size_exception(body, previous).startswith(body)

    new_with_exception = with_size_exception(body, "new reason")
    assert preserve_size_exception(new_with_exception, previous) == new_with_exception


def test_preserve_size_exception_stops_at_next_heading() -> None:
    previous = (
        "## Что изменено\n\n- old\n\n"
        "## Size exception\n\nlarge spec update\n\n"
        "## Проверки\n\n- pytest\n"
    )
    body = "## Что изменено\n\n- new\n"
    preserved = preserve_size_exception(body, previous)
    assert preserved == f"{body.rstrip()}\n\n## Size exception\n\nlarge spec update\n"
    assert "pytest" not in preserved


@pytest.mark.parametrize("reason", ["", "   ", "\t"])
def test_allow_large_requires_reason(reason: str) -> None:
    with pytest.raises(SystemExit):
        main(["--allow-large", reason])


def test_size_block_contains_stats() -> None:
    block = size_block(DiffSize(lines=12, files=1, generated_lines=9, generated_files=3))
    assert block.startswith(SIZE_BLOCK_START)
    assert block.endswith(SIZE_BLOCK_END)
    assert "12 строк, 1 файл" in block
    assert "9 строк, 3 файла" in block


def test_upsert_size_block_replaces_markers() -> None:
    body = (
        "## Размер\n\n"
        f"{SIZE_BLOCK_START}\n- old stats\n{SIZE_BLOCK_END}\n\n"
        "## Карта ревью\n\n- src/engine.py\n"
    )
    updated = upsert_size_block(body, DiffSize(lines=20, files=2))
    assert "- old stats" not in updated
    assert "20 строк, 2 файла" in updated
    assert updated.count(SIZE_BLOCK_START) == 1
    assert "## Карта ревью\n\n- src/engine.py" in updated


def test_upsert_size_block_appends_section() -> None:
    updated = upsert_size_block("## Что изменено\n\n- feat\n", DiffSize(lines=3, files=1))
    assert "## Что изменено" in updated
    assert "## Размер" in updated
    assert "3 строки, 1 файл" in updated


def test_upsert_size_block_keeps_tail_when_end_marker_missing() -> None:
    body = f"## Размер\n\n{SIZE_BLOCK_START}\n- stale stats\n\n## Карта ревью\n\n- src/engine.py\n"
    updated = upsert_size_block(body, DiffSize(lines=5, files=1))
    assert updated.count(SIZE_BLOCK_START) == 1
    assert updated.count(SIZE_BLOCK_END) == 1
    assert "- stale stats" not in updated
    assert "5 строк, 1 файл" in updated
    assert "## Карта ревью\n\n- src/engine.py" in updated


def test_upsert_size_block_replaces_dangling_marker_at_body_end() -> None:
    body = f"## Размер\n\n{SIZE_BLOCK_START}\n- stale stats\n"
    updated = upsert_size_block(body, DiffSize(lines=2, files=1))
    assert "- stale stats" not in updated
    assert "2 строки, 1 файл" in updated
    assert updated.count(SIZE_BLOCK_END) == 1


def test_upsert_size_block_preserves_legacy_content() -> None:
    body = "## Размер и карта ревью\n\nold manual text\n\n## Ревью\n\n- ok\n"
    updated = upsert_size_block(body, DiffSize(lines=7, files=1))
    assert "old manual text" in updated
    assert "## Ревью\n\n- ok" in updated
    assert "7 строк, 1 файл" in updated
    assert updated.count("## Размер") == 2


def test_upsert_size_block_preserves_size_exception() -> None:
    body = "## Что изменено\n\n- feat\n\n## Size exception\n\nlarge spec\n"
    updated = upsert_size_block(body, DiffSize(lines=3, files=1))
    assert "## Size exception\n\nlarge spec" in updated
    assert "3 строки, 1 файл" in updated


PREVIOUS_BODY = (
    "## Что изменено\n\n- feat: old work\n\n"
    "## Размер\n\n"
    f"{SIZE_BLOCK_START}\n- old stats\n{SIZE_BLOCK_END}\n\n"
    "## Карта ревью\n\n- src/engine.py\n"
)


def test_main_updates_existing_pr_and_keeps_title(monkeypatch: pytest.MonkeyPatch) -> None:
    git_calls: list[tuple[str, ...]] = []
    api_calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_git(*args: str) -> str:
        git_calls.append(args)
        responses: dict[tuple[str, ...], str] = {
            ("rev-parse", "--abbrev-ref", "HEAD"): "chore/example",
            ("fetch", "origin", "main"): "",
            ("remote", "get-url", "origin"): "git@github.com:SpiGit/eggpipe.git",
            ("ls-remote", "--heads", "origin", "chore/example"): "abc\trefs/heads/chore/example",
            ("log", "--format=%s", "origin/main..HEAD"): "feat: new work",
            ("diff", "--numstat", "-z", "origin/main...HEAD"): "12\t2\tsrc/engine.py\0",
        }
        return responses[args]

    def fake_api(
        method: str,
        path: str,
        token: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        api_calls.append((method, path, payload))
        if method == "GET" and path.startswith("/repos/SpiGit/eggpipe/pulls?head="):
            return [{"number": 42}]
        if method == "GET" and path == "/repos/SpiGit/eggpipe/pulls/42":
            return {"title": "Старый заголовок", "body": PREVIOUS_BODY}
        if method == "PATCH":
            return {"number": 42, "html_url": "https://github.com/SpiGit/eggpipe/pull/42"}
        raise AssertionError(f"unexpected API call: {method} {path}")

    monkeypatch.setattr(create_pr, "_run_git", fake_git)
    monkeypatch.setattr(create_pr, "_api", fake_api)
    monkeypatch.setattr(create_pr, "_token", lambda: "secret")

    assert main([]) == 0

    assert ("diff", "--numstat", "-z", "origin/main...HEAD") in git_calls
    assert all(method != "POST" for method, _, _ in api_calls)
    patches = [payload for method, _, payload in api_calls if method == "PATCH"]
    assert len(patches) == 1
    patch = patches[0]
    assert patch is not None
    assert patch["title"] == "Старый заголовок"
    body = patch["body"]
    assert isinstance(body, str)
    assert "## Что изменено\n\n- feat: old work" in body
    assert "## Карта ревью\n\n- src/engine.py" in body
    assert "- old stats" not in body
    assert "14 строк, 1 файл" in body
    assert body.count(SIZE_BLOCK_START) == 1
    assert body.count(SIZE_BLOCK_END) == 1
