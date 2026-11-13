"""Shared path filtering rules."""

from __future__ import annotations

IGNORED_PARTS = frozenset({".git", ".eggpipe", "__pycache__", ".venv", "node_modules"})


def is_ignored_part(part: str) -> bool:
    return part.startswith(".") or part in IGNORED_PARTS


__all__ = ["IGNORED_PARTS", "is_ignored_part"]
