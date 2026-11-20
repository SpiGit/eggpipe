"""Watch mode with a lazily imported watchdog."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from typing_extensions import override

from eggpipe.core.paths import is_ignored_part
from eggpipe.utils.exceptions import ConfigValidationError

LOGGER = logging.getLogger(__name__)

# ADR-0019 G3: max_delay is a derived internal cap, not user-configurable.
MAX_DELAY_MULTIPLIER = 10


def should_ignore(path: Path, ignored_dirs: set[Path], *, allow: set[Path]) -> bool:
    resolved = path.resolve()
    if resolved in allow:
        return False
    if any(is_ignored_part(part) for part in resolved.parts):
        return True
    return any(
        resolved == directory or resolved.is_relative_to(directory) for directory in ignored_dirs
    )


class _Debouncer:
    """Trailing debounce with a bounded burst window (ADR-0019).

    Invariants: at most one scheduled run (G2), at most one running callback
    (G1), a run starts no later than ``max_delay_ms`` after the first event of
    a burst (G3), and events during a run yield exactly one follow-up (G4).
    After :meth:`stop`, scheduled runs are cancelled and new triggers are
    suppressed; :meth:`wait_idle` then blocks only for the running callback.
    """

    def __init__(
        self,
        callback: Callable[[], None],
        delay_ms: int,
        max_delay_ms: int | None = None,
    ) -> None:
        self._callback = callback
        self._delay = delay_ms / 1000
        if max_delay_ms is None:
            max_delay_ms = MAX_DELAY_MULTIPLIER * delay_ms
        self._max_delay = max_delay_ms / 1000
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._idle = threading.Condition(self._lock)
        self._running = False
        self._pending = False
        self._stopped = False
        self._burst_start: float | None = None

    def trigger(self) -> None:
        with self._lock:
            self._trigger_locked()

    def stop(self) -> None:
        """Cancel the scheduled run and suppress further triggers."""
        with self._lock:
            self._stopped = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._idle.notify_all()

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Block until no callback is running and no timer is armed."""
        with self._idle:
            return self._idle.wait_for(
                lambda: not self._running and self._timer is None, timeout=timeout
            )

    def _trigger_locked(self) -> None:
        if self._stopped:
            return
        now = time.monotonic()
        if self._burst_start is None:
            self._burst_start = now
        # G3: cap the trailing delay so a continuous event stream cannot
        # starve the run beyond max_delay from the first burst event.
        delay = min(self._delay, max(self._max_delay - (now - self._burst_start), 0.0))
        if self._timer is not None:
            self._timer.cancel()
        timer = threading.Timer(delay, self._fire)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _fire(self) -> None:
        with self._lock:
            if self._timer is threading.current_thread():
                self._timer = None
            if self._stopped:
                self._idle.notify_all()
                return
            if self._running:
                self._pending = True
                return
            self._running = True
            # The burst window closes: this run reflects its events. Events
            # arriving during the run keep the old burst start, so the
            # follow-up fires promptly once the run completes (G3/G4).
            self._burst_start = None
        try:
            self._callback()
        except Exception:  # watch mode must survive a single error
            LOGGER.exception("watch generation failed")
        finally:
            with self._lock:
                self._running = False
                if self._pending and not self._stopped:
                    self._pending = False
                    self._trigger_locked()
                else:
                    self._pending = False
                    self._idle.notify_all()


@dataclass
class WatchRunner:
    config_path: Path
    source_paths: list[Path]
    ignored_dirs: set[Path]
    debounce_ms: int
    run_once: Callable[[], int]
    stop_event: threading.Event | None = None
    max_delay_ms: int | None = None
    _debouncer: _Debouncer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._debouncer = _Debouncer(self._fire, self.debounce_ms, self.max_delay_ms)

    def run(self) -> int:
        try:
            from watchdog.observers import Observer
        except ImportError as exc:
            raise ConfigValidationError(
                "watchdog is not installed; run pip install 'eggpipe[watch]'"
            ) from exc

        handler = _make_handler(self)
        observer = Observer()
        scheduled: set[Path] = set()
        for path in [*self.source_paths, self.config_path]:
            directory = path if path.is_dir() else path.parent
            directory = directory.resolve()
            if directory in scheduled:
                continue
            scheduled.add(directory)
            observer.schedule(handler, str(directory), recursive=path.is_dir())
        self.run_once()
        observer.start()
        try:
            while observer.is_alive():
                if self.stop_event is not None and self.stop_event.is_set():
                    break
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        observer.stop()
        observer.join()
        # ADR-0019: cancel scheduled runs, then let the current run finish so
        # artifact writes and the JSON Lines report are not cut off mid-commit.
        # A second KeyboardInterrupt here propagates and exits with 130.
        self._debouncer.stop()
        self._debouncer.wait_idle()
        return 0

    def _fire(self) -> None:
        self.run_once()

    def _on_event(self, path: Path, is_directory: bool) -> None:
        if is_directory:
            return
        if not _relevant(path, self.config_path, self.source_paths):
            return
        if should_ignore(path, self.ignored_dirs, allow={self.config_path.resolve()}):
            return
        self._debouncer.trigger()


def _make_handler(runner: WatchRunner) -> Any:
    from watchdog.events import FileSystemEventHandler

    class Handler(FileSystemEventHandler):
        @override
        def on_any_event(self, event: object) -> None:
            path = Path(str(getattr(event, "src_path", "")))
            runner._on_event(path, bool(getattr(event, "is_directory", False)))

    return Handler()


def run_watch(
    *,
    config_path: Path,
    source_paths: list[Path],
    ignored_dirs: set[Path],
    debounce_ms: int,
    run_once: Callable[[], int],
    stop_event: threading.Event | None = None,
    max_delay_ms: int | None = None,
) -> int:
    return WatchRunner(
        config_path=config_path,
        source_paths=source_paths,
        ignored_dirs=ignored_dirs,
        debounce_ms=debounce_ms,
        run_once=run_once,
        stop_event=stop_event,
        max_delay_ms=max_delay_ms,
    ).run()


def _relevant(path: Path, config_path: Path, source_paths: list[Path]) -> bool:
    resolved = path.resolve()
    if resolved == config_path.resolve():
        return True
    for source in source_paths:
        source = source.resolve()
        if source.is_dir() and resolved.is_relative_to(source):
            return True
        if resolved == source:
            return True
    return False


__all__ = ["WatchRunner", "run_watch", "should_ignore"]
