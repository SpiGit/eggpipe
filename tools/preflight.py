#!/usr/bin/env python3
"""Run the checks that must pass before commit or push."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys


def clean_env() -> dict[str, str]:
    """Return the environment without the GIT_ namespace set by git hooks.

    Hooks can set GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE and other GIT_* variables.
    Tests that create temporary repositories must not inherit them.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


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
    args = parser.parse_args(argv)
    if shutil.which("uv") is None:
        print("preflight: uv is not installed or not in PATH", file=sys.stderr)
        return 127

    for command in commands(fast=args.fast):
        print(f"$ {shlex.join(command)}", flush=True)
        result = subprocess.run(command, check=False, env=clean_env())
        if result.returncode != 0:
            print(f"preflight failed: {shlex.join(command)}", file=sys.stderr)
            return result.returncode
    print("preflight: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
