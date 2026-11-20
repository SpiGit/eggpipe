"""Integration test for the watch loop."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from eggpipe.watch.watcher import run_watch


def wait(event: threading.Event, timeout: float = 3.0) -> bool:
    return event.wait(timeout)


def test_watch_rebuilds_after_change(tmp_path: Path) -> None:
    source = tmp_path / "model.yaml"
    source.write_text("format: entity-model\nversion: '1.0'\nmodel: {}\n", encoding="utf-8")
    config = tmp_path / ".eggpipe.yaml"
    config.write_text(
        "version: '1.0'\nsources:\n  - path: ./model.yaml\n    layout: monolith\ngenerators: []\n",
        encoding="utf-8",
    )
    initial = threading.Event()
    rebuilt = threading.Event()
    runs = {"count": 0}

    def run_once() -> int:
        runs["count"] += 1
        if runs["count"] == 1:
            initial.set()
        else:
            rebuilt.set()
        return 0

    stop = threading.Event()
    thread = threading.Thread(
        target=run_watch,
        kwargs={
            "config_path": config,
            "source_paths": [source],
            "ignored_dirs": set(),
            "debounce_ms": 50,
            "run_once": run_once,
            "stop_event": stop,
        },
        daemon=True,
    )
    thread.start()
    assert wait(initial)
    time.sleep(0.2)
    source.write_text(
        "format: entity-model\nversion: '1.0'\nmodel:\n  entities: []\n",
        encoding="utf-8",
    )
    assert wait(rebuilt)
    stop.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert runs["count"] >= 2


def test_watch_stop_waits_for_current_run(tmp_path: Path) -> None:
    """ADR-0019: stop during a run cancels scheduled runs and waits for the current one."""
    source = tmp_path / "model.yaml"
    source.write_text("format: entity-model\nversion: '1.0'\nmodel: {}\n", encoding="utf-8")
    config = tmp_path / ".eggpipe.yaml"
    config.write_text(
        "version: '1.0'\nsources:\n  - path: ./model.yaml\n    layout: monolith\ngenerators: []\n",
        encoding="utf-8",
    )
    runs = {"count": 0}
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def run_once() -> int:
        runs["count"] += 1
        if runs["count"] > 1:
            started.set()
            release.wait(5.0)
            completed.set()
        return 0

    stop = threading.Event()
    exit_codes: list[int] = []
    thread = threading.Thread(
        target=lambda: exit_codes.append(
            run_watch(
                config_path=config,
                source_paths=[source],
                ignored_dirs=set(),
                debounce_ms=30,
                run_once=run_once,
                stop_event=stop,
            )
        ),
        daemon=True,
    )
    thread.start()
    time.sleep(0.2)  # let the initial run finish and the observer start
    source.write_text(
        "format: entity-model\nversion: '1.0'\nmodel:\n  entities: []\n",
        encoding="utf-8",
    )
    assert wait(started)
    stop.set()
    time.sleep(0.2)
    assert thread.is_alive()  # still waiting for the running callback
    assert exit_codes == []
    release.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert exit_codes == [0]
    assert completed.is_set()
    assert runs["count"] == 2
