"""Shared helpers for the test suite."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

import pytest

from eggpipe.engine import plugin_loader

EntryPointT = TypeVar("EntryPointT")


def patch_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    entries: Sequence[EntryPointT],
    expected_group: str,
) -> None:
    """Replace plugin entry points, returning entries only for the expected group."""

    def fake_entry_points(*, group: str) -> list[EntryPointT]:
        return list(entries) if group == expected_group else []

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
