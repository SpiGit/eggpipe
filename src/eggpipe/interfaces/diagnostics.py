"""Structured core diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DiagnosticLocation(BaseModel):
    """Where the diagnostic originated."""

    file: Path | None = None
    entity: str | None = None
    field: str | None = None
    path: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class Diagnostic(BaseModel):
    """Validation diagnostic; the code is stable and documented."""

    level: Literal["warning", "error"]
    code: str
    message: str
    location: DiagnosticLocation | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def error(
        cls,
        code: str,
        message: str,
        *,
        file: Path | None = None,
        entity: str | None = None,
        field: str | None = None,
        path: str | None = None,
    ) -> Diagnostic:
        return cls._make(
            "error",
            code,
            message,
            file=file,
            entity=entity,
            field=field,
            path=path,
        )

    @classmethod
    def warning(
        cls,
        code: str,
        message: str,
        *,
        file: Path | None = None,
        entity: str | None = None,
        field: str | None = None,
        path: str | None = None,
    ) -> Diagnostic:
        return cls._make(
            "warning",
            code,
            message,
            file=file,
            entity=entity,
            field=field,
            path=path,
        )

    @classmethod
    def _make(
        cls,
        level: Literal["warning", "error"],
        code: str,
        message: str,
        *,
        file: Path | None = None,
        entity: str | None = None,
        field: str | None = None,
        path: str | None = None,
    ) -> Diagnostic:
        return cls(
            level=level,
            code=code,
            message=message,
            location=DiagnosticLocation(file=file, entity=entity, field=field, path=path),
        )


def error(
    code: str,
    message: str,
    *,
    file: Path | None = None,
    entity: str | None = None,
    field: str | None = None,
    path: str | None = None,
) -> Diagnostic:
    return Diagnostic.error(
        code,
        message,
        file=file,
        entity=entity,
        field=field,
        path=path,
    )


def warning(
    code: str,
    message: str,
    *,
    file: Path | None = None,
    entity: str | None = None,
    field: str | None = None,
    path: str | None = None,
) -> Diagnostic:
    return Diagnostic.warning(
        code,
        message,
        file=file,
        entity=entity,
        field=field,
        path=path,
    )
