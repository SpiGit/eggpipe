#!/usr/bin/env python3
"""Prepare a release: bump the package version and cut a CHANGELOG section.

The script is the single entry point for release preparation. It keeps the
hand-written version in one place (``pyproject.toml``), mirrors it into
``src/eggpipe/version.py``, cuts ``[Unreleased]`` in ``CHANGELOG.md`` and
regenerates ``docs/ai``. Documentation must not hardcode the current version:
``tools/check_docs.py`` rejects it outside an allowlist (DOC130).

Usage:
    python tools/bump_version.py 0.5.0
    python tools/bump_version.py 0.5.0 --date 2026-11-20 --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_FILE = ROOT / "src" / "eggpipe" / "version.py"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PROJECT_VERSION = re.compile(r'(?m)^version = "([^"]+)"')
VERSION_LITERAL = re.compile(r'(?m)^__version__ = "([^"]+)"')
UNRELEASED = "## [Unreleased]\n"


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER.match(value)
    if match is None:
        raise ValueError(f"invalid SemVer: {value!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def read_version(text: str, pattern: re.Pattern[str], source: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"version not found in {source}")
    return match.group(1)


def bump_pyproject(text: str, version: str) -> str:
    updated, count = PROJECT_VERSION.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise ValueError("failed to update pyproject.toml")
    return updated


def bump_version_file(text: str, version: str) -> str:
    updated, count = VERSION_LITERAL.subn(f'__version__ = "{version}"', text, count=1)
    if count != 1:
        raise ValueError("failed to update version.py")
    return updated


def cut_changelog(text: str, version: str, date: str) -> str:
    heading = f"## [{version}] - {date}\n"
    if f"## [{version}]" in text:
        raise ValueError(f"CHANGELOG already has a section for {version}")
    if UNRELEASED not in text:
        raise ValueError("CHANGELOG has no [Unreleased] section")
    return text.replace(UNRELEASED, f"{UNRELEASED}\n{heading}", 1)


def render_summary(changes: list[tuple[Path, str]], version: str) -> str:
    lines = [f"version: {version}"]
    lines += [f"updated: {path.relative_to(ROOT)}" for path, _ in changes]
    lines += [
        "",
        "next steps:",
        "  1. review `git diff` and run `uv run python tools/preflight.py`",
        "  2. open a release PR and merge it",
        f"  3. tag `v{version}` on main and push the tag",
    ]
    return "\n".join(lines)


def write(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a release")
    parser.add_argument("version", help="new SemVer version, for example 0.5.0")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    version_text = VERSION_FILE.read_text(encoding="utf-8")
    changelog_text = CHANGELOG.read_text(encoding="utf-8")

    try:
        current = read_version(pyproject_text, PROJECT_VERSION, "pyproject.toml")
        parse_semver(args.version)
        if parse_semver(args.version) <= parse_semver(current):
            raise ValueError(f"new version {args.version} must be greater than {current}")
        new_pyproject = bump_pyproject(pyproject_text, args.version)
        new_version_file = bump_version_file(version_text, args.version)
        new_changelog = cut_changelog(changelog_text, args.version, args.date)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    changes = [
        (PYPROJECT, new_pyproject),
        (VERSION_FILE, new_version_file),
        (CHANGELOG, new_changelog),
    ]
    for path, content in changes:
        write(path, content, args.dry_run)

    if not args.dry_run:
        for command in (["uv", "lock"], ["uv", "run", "python", "tools/build_ai_docs.py"]):
            result = subprocess.run(command, cwd=ROOT, check=False)
            if result.returncode != 0:
                print(f"error: failed to run {' '.join(command)}", file=sys.stderr)
                return result.returncode

    print(render_summary(changes, args.version))
    if args.dry_run:
        print("dry run: no files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
