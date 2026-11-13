"""Watch-режим с lazy-import watchdog."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from typing_extensions import override

from eggpipe.utils.exceptions import ConfigValidationError

IGNORED_PARTS = {".git", ".eggpipe", "__pycache__", ".venv", "node_modules"}


def should_ignore(path: Path, ignored_dirs: set[Path], *, allow: set[Path]) -> bool:
    resolved = path.resolve()
    if resolved in allow:
        return False
    if any(part in IGNORED_PARTS or part.startswith(".") for part in resolved.parts):
        return True
    return any(
        resolved == directory or resolved.is_relative_to(directory) for directory in ignored_dirs
    )


def run_watch(
    *,
    config_path: Path,
    source_paths: list[Path],
    ignored_dirs: set[Path],
    debounce_ms: int,
    run_once: Callable[[], int],
    stop_event: threading.Event | None = None,
) -> int:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise ConfigValidationError(
            "watchdog не установлен; используйте pip install 'eggpipe[watch]'"
        ) from exc

    class Handler(FileSystemEventHandler):
        def __init__(self) -> None:
            self._timer: threading.Timer | None = None

        @override
        def on_any_event(self, event: object) -> None:
            if getattr(event, "is_directory", False):
                return
            raw_path = getattr(event, "src_path", "")
            path = Path(str(raw_path))
            if not _relevant(path, config_path, source_paths):
                return
            if should_ignore(path, ignored_dirs, allow={config_path.resolve()}):
                return
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(debounce_ms / 1000, self._fire)
            self._timer.daemon = True
            self._timer.start()

        def _fire(self) -> None:
            try:
                run_once()
            except Exception as exc:  # watch не должен падать от одной ошибки
                print(f"watch error: {exc}", flush=True)

    handler = Handler()
    observer = Observer()
    scheduled: set[Path] = set()
    for path in [*source_paths, config_path]:
        directory = path if path.is_dir() else path.parent
        directory = directory.resolve()
        if directory in scheduled:
            continue
        scheduled.add(directory)
        observer.schedule(handler, str(directory), recursive=path.is_dir())
    run_once()
    observer.start()
    try:
        while observer.is_alive():
            if stop_event is not None and stop_event.is_set():
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    observer.stop()
    observer.join()
    return 0


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


__all__ = ["run_watch", "should_ignore"]
