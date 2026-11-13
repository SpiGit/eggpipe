"""Tests for watch filters."""

from __future__ import annotations

from pathlib import Path

from eggpipe.watch.watcher import should_ignore


def test_ignore_hidden_and_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    source = tmp_path / "model.yaml"
    assert should_ignore(source, {output}, allow=set()) is False
    assert should_ignore(output / "generated.py", {output}, allow=set()) is True
    assert should_ignore(tmp_path / ".git" / "index", set(), allow=set()) is True
    assert (
        should_ignore(tmp_path / ".eggpipe.yaml", set(), allow={tmp_path / ".eggpipe.yaml"})
        is False
    )
