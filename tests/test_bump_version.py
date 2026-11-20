"""Tests for the release bump script."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from tools import bump_version
from tools.bump_version import (
    bump_pyproject,
    bump_version_file,
    cut_changelog,
    parse_semver,
    validate_date,
)

PYPROJECT = """[build-system]
requires = ["hatchling"]

[project]
name = "eggpipe"
version = "0.4.0"
dependencies = ["pydantic>=2"]
"""

VERSION_FILE = '"""Package version."""\n\n__version__ = "0.4.0"\n'

CHANGELOG = """# Changelog

## [Unreleased]

### Changed

- something new

## [0.4.0] - 2026-11-18

### Added

- previous release
"""


class TestParseSemver(unittest.TestCase):
    def test_accepts_three_numbers(self) -> None:
        self.assertEqual(parse_semver("1.2.3"), (1, 2, 3))

    def test_rejects_partial_version(self) -> None:
        with self.assertRaises(ValueError):
            parse_semver("1.2")

    def test_rejects_prerelease(self) -> None:
        with self.assertRaises(ValueError):
            parse_semver("1.2.3-rc1")


class TestValidateDate(unittest.TestCase):
    def test_accepts_iso_date(self) -> None:
        self.assertEqual(validate_date("2026-11-20"), "2026-11-20")

    def test_rejects_garbage(self) -> None:
        with self.assertRaises(ValueError):
            validate_date("20.11.2026")


class TestBumpPyproject(unittest.TestCase):
    def test_replaces_project_version(self) -> None:
        updated = bump_pyproject(PYPROJECT, "0.5.0")
        self.assertIn('version = "0.5.0"', updated)
        self.assertNotIn('version = "0.4.0"', updated)

    def test_keeps_other_fields(self) -> None:
        updated = bump_pyproject(PYPROJECT, "0.5.0")
        self.assertIn('dependencies = ["pydantic>=2"]', updated)
        self.assertIn('name = "eggpipe"', updated)

    def test_requires_version_field(self) -> None:
        with self.assertRaises(ValueError):
            bump_pyproject("[project]\nname = 'x'\n", "0.5.0")


class TestBumpVersionFile(unittest.TestCase):
    def test_replaces_literal(self) -> None:
        self.assertIn('__version__ = "0.5.0"', bump_version_file(VERSION_FILE, "0.5.0"))

    def test_requires_literal(self) -> None:
        with self.assertRaises(ValueError):
            bump_version_file('"""doc"""\n', "0.5.0")


class TestCutChangelog(unittest.TestCase):
    def test_cuts_release_section(self) -> None:
        updated = cut_changelog(CHANGELOG, "0.5.0", "2026-11-20")
        self.assertIn("## [0.5.0] - 2026-11-20", updated)
        self.assertIn("- something new", updated)
        self.assertTrue(updated.startswith("# Changelog\n\n## [Unreleased]\n\n## [0.5.0]"))
        self.assertIn("## [0.4.0] - 2026-11-18", updated)

    def test_keeps_unreleased_empty(self) -> None:
        updated = cut_changelog(CHANGELOG, "0.5.0", "2026-11-20")
        before_release = updated.split("## [0.5.0]")[0]
        self.assertNotIn("- something new", before_release)

    def test_rejects_duplicate_version(self) -> None:
        with self.assertRaises(ValueError):
            cut_changelog(CHANGELOG, "0.4.0", "2026-11-20")

    def test_requires_unreleased_section(self) -> None:
        with self.assertRaises(ValueError):
            cut_changelog("# Changelog\n\n## [0.4.0] - 2026-11-18\n", "0.5.0", "2026-11-20")


class TestMain(unittest.TestCase):
    def workspace(self, root: Path) -> tuple[Path, Path, Path]:
        pyproject = root / "pyproject.toml"
        pyproject.write_text(PYPROJECT, encoding="utf-8")
        version_file = root / "version.py"
        version_file.write_text(VERSION_FILE, encoding="utf-8")
        changelog = root / "CHANGELOG.md"
        changelog.write_text(CHANGELOG, encoding="utf-8")
        return pyproject, version_file, changelog

    @contextlib.contextmanager
    def patched(self, root: Path, paths: tuple[Path, Path, Path], run: Any):
        with mock.patch.multiple(
            bump_version,
            ROOT=root,
            PYPROJECT=paths[0],
            VERSION_FILE=paths[1],
            CHANGELOG=paths[2],
            subprocess=SimpleNamespace(run=run),
        ):
            yield

    def run_main(
        self, argv: list[str], root: Path, paths: tuple[Path, Path, Path], run: Any
    ) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            self.patched(root, paths, run),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = bump_version.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.workspace(root)
            run = mock.Mock()
            code, stdout, _stderr = self.run_main(["0.5.0", "--dry-run"], root, paths, run)
            self.assertEqual(code, 0)
            self.assertIn("dry run: no files changed", stdout)
            run.assert_not_called()
            self.assertIn('version = "0.4.0"', paths[0].read_text(encoding="utf-8"))
            self.assertIn('__version__ = "0.4.0"', paths[1].read_text(encoding="utf-8"))
            self.assertNotIn("## [0.5.0]", paths[2].read_text(encoding="utf-8"))

    def test_rejects_version_not_greater(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.workspace(root)
            code, _stdout, stderr = self.run_main(["0.4.0"], root, paths, mock.Mock())
            self.assertEqual(code, 2)
            self.assertIn("must be greater than 0.4.0", stderr)
            self.assertIn('version = "0.4.0"', paths[0].read_text(encoding="utf-8"))

    def test_reports_partial_failure_after_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.workspace(root)
            run = mock.Mock(return_value=SimpleNamespace(returncode=1))
            code, _stdout, stderr = self.run_main(["0.5.0"], root, paths, run)
            self.assertEqual(code, 1)
            self.assertIn("files are already updated", stderr)
            self.assertEqual(run.call_count, 1)
            self.assertIn('version = "0.5.0"', paths[0].read_text(encoding="utf-8"))
            self.assertIn("## [0.5.0]", paths[2].read_text(encoding="utf-8"))

    def test_success_runs_post_steps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.workspace(root)
            run = mock.Mock(return_value=SimpleNamespace(returncode=0))
            code, stdout, _stderr = self.run_main(["0.5.0"], root, paths, run)
            self.assertEqual(code, 0)
            self.assertEqual(
                run.call_args_list,
                [
                    mock.call(["uv", "lock"], cwd=root, check=False),
                    mock.call(
                        ["uv", "run", "python", "tools/build_ai_docs.py"],
                        cwd=root,
                        check=False,
                    ),
                ],
            )
            self.assertIn("tag `v0.5.0`", stdout)


if __name__ == "__main__":
    unittest.main()
