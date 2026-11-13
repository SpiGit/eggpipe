"""Source provenance: the last git commit of a file."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Provenance:
    path: Path
    commit: str | None
    date: datetime | None


def git_provenance(path: Path) -> Provenance | None:
    """Return commit/date for a file, or None when git/history is unavailable."""
    resolved = path.resolve()
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(resolved.parent),
                "log",
                "-1",
                "--format=%H%n%cI",
                "--",
                resolved.name,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = [line for line in result.stdout.splitlines() if line]
    if len(lines) < 2:
        return None
    try:
        date = datetime.fromisoformat(lines[1].replace("Z", "+00:00"))
    except ValueError:
        date = None
    return Provenance(path=resolved, commit=lines[0], date=date)


__all__ = ["Provenance", "git_provenance"]
