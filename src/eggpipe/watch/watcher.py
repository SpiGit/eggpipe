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
    def __init__(self, callback: Callable[[], None], delay_ms: int) -> None:
        self._callback = callback
        self._delay = delay_ms / 1000
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._running = False
        self._pending = False

    def trigger(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._delay, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            if self._running:
                self._pending = True
                return
            self._running = True
        try:
            self._callback()
        except Exception:  # watch mode must survive a single error
            LOGGER.exception("watch generation failed")
        finally:
            with self._lock:
                self._running = False
                pending = self._pending
                self._pending = False
            if pending:
                self.trigger()


@dataclass
class WatchRunner:
    config_path: Path
    source_paths: list[Path]
    ignored_dirs: set[Path]
    debounce_ms: int
    run_once: Callable[[], int]
    stop_event: threading.Event | None = None
    _debouncer: _Debouncer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._debouncer = _Debouncer(self._fire, self.debounce_ms)

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
) -> int:
    return WatchRunner(
        config_path=config_path,
        source_paths=source_paths,
        ignored_dirs=ignored_dirs,
        debounce_ms=debounce_ms,
        run_once=run_once,
        stop_event=stop_event,
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
