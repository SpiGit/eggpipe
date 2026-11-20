#!/usr/bin/env python3
"""Run the checks that must pass before commit or push."""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = ROOT / ".git" / "eggpipe-preflight.stamp"
HASHED_PATHS = (
    "src",
    "tests",
    "tools",
    "examples",
    "docs",
    "engineering",
    ".github",
    "pyproject.toml",
    "uv.lock",
    "mkdocs.yml",
    "AGENTS.md",
    "CONTRIBUTING.md",
)
SKIP_PARTS = {".git", ".venv", "__pycache__", "dist", "build", "site", ".pytest_cache", ".local"}


def clean_env() -> dict[str, str]:
    """Return the environment without the GIT_ namespace set by git hooks.

    Hooks can set GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE and other GIT_* variables.
    Tests that create temporary repositories must not inherit them.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def tree_hash(root: Path) -> str:
    """Return a content hash of the inputs that affect preflight results."""
    digest = hashlib.sha256()
    for name in HASHED_PATHS:
        path = root / name
        if not path.exists():
            continue
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in candidates:
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(root)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            try:
                digest.update(candidate.read_bytes())
            except OSError:
                continue
            digest.update(b"\0")
    return digest.hexdigest()


def is_unchanged(stamp: Path, current: str) -> bool:
    """Return True when the stamp exists and matches the current tree."""
    try:
        return stamp.read_text(encoding="utf-8").strip() == current
    except OSError:
        return False


def commands(*, fast: bool) -> list[list[str]]:
    """Return the ordered command list."""
    checks = [
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "src", "tests", "tools", "examples"],
    ]
    if fast:
        return checks
    return [
        *checks,
        ["uv", "run", "pyrefly", "check"],
        ["uv", "run", "pytest", "-q"],
        ["uv", "run", "python", "tools/check_docs.py", "--strict"],
        ["uv", "run", "mkdocs", "build", "--strict"],
        ["uv", "build"],
        ["uv", "run", "python", "tools/check_wheel.py", "dist"],
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Eggpipe preflight checks")
    parser.add_argument("--fast", action="store_true", help="only lint and format checks")
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="skip heavy checks when the tree is unchanged since the last successful run",
    )
    args = parser.parse_args(argv)
    if shutil.which("uv") is None:
        print("preflight: uv is not installed or not in PATH", file=sys.stderr)
        return 127

    current = tree_hash(ROOT) if args.stamp else ""
    heavy_skipped = args.stamp and not args.fast and is_unchanged(STAMP, current)
    if heavy_skipped:
        print("preflight: tree unchanged, running fast checks only")

    for command in commands(fast=args.fast or heavy_skipped):
        print(f"$ {shlex.join(command)}", flush=True)
        result = subprocess.run(command, check=False, env=clean_env())
        if result.returncode != 0:
            print(f"preflight failed: {shlex.join(command)}", file=sys.stderr)
            if args.stamp:
                STAMP.unlink(missing_ok=True)
            return result.returncode
    if args.stamp and not args.fast and not heavy_skipped:
        STAMP.write_text(current + "\n", encoding="utf-8")
    print("preflight: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
