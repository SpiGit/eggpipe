"""Atomic JSON writers for internal state files."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_json_atomic(
    path: Path,
    value: BaseModel | dict[str, Any],
    *,
    compact: bool = False,
    durable: bool = True,
) -> None:
    """Write JSON through a temporary file and ``os.replace``.

    ``durable`` also fsyncs file and directory; internal caches pass ``False``.
    """
    data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            if durable:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(temporary, path)
        if durable:
            fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


__all__ = ["fsync_directory", "write_json_atomic"]
