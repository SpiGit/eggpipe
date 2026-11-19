"""Tests for the release bump script."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
