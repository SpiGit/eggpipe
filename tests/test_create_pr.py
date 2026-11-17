"""Tests for the pull request helper."""

from __future__ import annotations

import pytest
from tools.create_pr import (
    MAX_PR_FILES,
    MAX_PR_LINES,
    SIZE_BLOCK_END,
    SIZE_BLOCK_START,
    DiffSize,
    _numstat_path,
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


def test_numstat_path_rename() -> None:
    assert _numstat_path("src/old.py => src/new.py") == "src/new.py"
    assert _numstat_path("{src/old => src/new}/engine.py") == "src/new/engine.py"
    assert _numstat_path("{src => docs/ai}/llms.txt") == "docs/ai/llms.txt"


def test_parse_numstat_uses_rename_destination() -> None:
    size = parse_numstat("1\t1\tsrc/old.py => src/new.py\n2\t0\t{src => docs/ai}/llms.txt\n")
    assert size.lines == 2
    assert size.files == 1
    assert size.generated_lines == 2
    assert size.generated_files == 1


def test_numstat_path_quoted() -> None:
    assert _numstat_path('"docs/ai/weird\\tname.txt"') == "docs/ai/weird\tname.txt"
    assert _numstat_path('"src/quo\\"te.py"') == 'src/quo"te.py'
    assert _numstat_path('"src/back\\\\slash.py"') == "src/back\\slash.py"
    assert _numstat_path('"src/old.py" => "src/new.py"') == "src/new.py"


def test_parse_numstat_quoted_generated() -> None:
    size = parse_numstat('4\t0\t"docs/ai/weird\\tname.txt"\n')
    assert size.lines == 0
    assert size.files == 0
    assert size.generated_lines == 4
    assert size.generated_files == 1


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
