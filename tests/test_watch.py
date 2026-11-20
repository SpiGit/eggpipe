"""Tests for watch filters and debounce scheduling (ADR-0019)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from eggpipe.watch.watcher import _Debouncer, should_ignore


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


def test_debouncer_coalesces_burst_into_single_run() -> None:
    """G2: a burst of events at rest yields exactly one run."""
    calls: list[int] = []
    debouncer = _Debouncer(lambda: calls.append(1), delay_ms=50, max_delay_ms=500)
    for _ in range(5):
        debouncer.trigger()
        time.sleep(0.01)
    assert debouncer.wait_idle(timeout=3.0)
    assert len(calls) == 1
    debouncer.stop()


def test_debouncer_max_delay_caps_starvation() -> None:
    """G3: a continuous event stream cannot postpone the run beyond max_delay."""
    started = threading.Event()
    debouncer = _Debouncer(started.set, delay_ms=50, max_delay_ms=100)
    stop_spam = threading.Event()

    def spam() -> None:
        while not stop_spam.is_set():
            debouncer.trigger()
            time.sleep(0.01)

    spammer = threading.Thread(target=spam, daemon=True)
    first = time.monotonic()
    spammer.start()
    try:
        assert started.wait(3.0)
        elapsed = time.monotonic() - first
    finally:
        stop_spam.set()
        spammer.join(timeout=1.0)
        debouncer.stop()
        debouncer.wait_idle(timeout=1.0)
    # max_delay is 100 ms; allow generous slack for slow CI machines.
    assert elapsed < 1.0


def test_debouncer_event_during_run_yields_single_followup() -> None:
    """G1/G4: no concurrent runs and exactly one follow-up after the run."""
    lock = threading.Lock()
    calls: list[int] = []
    active = 0
    max_active = 0
    started = threading.Event()
    release = threading.Event()

    def callback() -> None:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            calls.append(1)
            first = len(calls) == 1
        if first:
            started.set()
            release.wait(3.0)
        with lock:
            active -= 1

    debouncer = _Debouncer(callback, delay_ms=10, max_delay_ms=200)
    debouncer.trigger()
    try:
        assert started.wait(3.0)
        for _ in range(3):
            debouncer.trigger()
            time.sleep(0.005)
        release.set()
        assert debouncer.wait_idle(timeout=3.0)
    finally:
        debouncer.stop()
    assert max_active == 1
    assert len(calls) == 2


def test_debouncer_followup_starts_promptly_after_long_run() -> None:
    """G3: events during a long run start the follow-up within debounce after it."""
    marks: list[tuple[str, float]] = []
    started = threading.Event()
    release = threading.Event()

    def callback() -> None:
        marks.append(("start", time.monotonic()))
        if len(marks) == 1:
            started.set()
            release.wait(3.0)
        marks.append(("end", time.monotonic()))

    debouncer = _Debouncer(callback, delay_ms=30, max_delay_ms=300)
    debouncer.trigger()
    try:
        assert started.wait(3.0)
        debouncer.trigger()  # event during the long run
        time.sleep(0.05)
        release.set()
        assert debouncer.wait_idle(timeout=3.0)
    finally:
        debouncer.stop()
    assert [name for name, _ in marks] == ["start", "end", "start", "end"]
    gap = marks[2][1] - marks[1][1]
    assert gap < 0.2


def test_debouncer_survives_callback_error() -> None:
    """Regression: an error in one run does not stop subsequent runs."""
    calls: list[int] = []

    def callback() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    debouncer = _Debouncer(callback, delay_ms=10, max_delay_ms=100)
    try:
        debouncer.trigger()
        assert debouncer.wait_idle(timeout=3.0)
        debouncer.trigger()
        assert debouncer.wait_idle(timeout=3.0)
    finally:
        debouncer.stop()
    assert len(calls) == 2


def test_debouncer_stop_cancels_scheduled_run() -> None:
    """ADR-0019 stop boundary: a scheduled run is cancelled, triggers suppressed."""
    calls: list[int] = []
    debouncer = _Debouncer(lambda: calls.append(1), delay_ms=30, max_delay_ms=300)
    debouncer.trigger()
    debouncer.stop()
    assert debouncer.wait_idle(timeout=1.0)
    time.sleep(0.1)
    assert calls == []
    debouncer.trigger()  # suppressed after stop
    assert debouncer.wait_idle(timeout=1.0)
    time.sleep(0.1)
    assert calls == []


def test_debouncer_stop_waits_for_running_callback() -> None:
    """ADR-0019 stop boundary: the current run is never interrupted."""
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def callback() -> None:
        started.set()
        release.wait(3.0)
        finished.set()

    debouncer = _Debouncer(callback, delay_ms=10, max_delay_ms=100)
    debouncer.trigger()
    try:
        assert started.wait(3.0)
        debouncer.stop()
        idle = threading.Event()

        def waiter() -> None:
            debouncer.wait_idle(timeout=3.0)
            idle.set()

        thread = threading.Thread(target=waiter, daemon=True)
        thread.start()
        assert not idle.wait(0.1)  # still blocked by the running callback
        release.set()
        assert idle.wait(3.0)
        assert finished.is_set()
    finally:
        debouncer.stop()
