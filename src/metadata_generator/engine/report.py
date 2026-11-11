"""Модель отчёта Engine."""

from __future__ import annotations

from typing import Literal

import pydantic as pyd
from pydantic import ConfigDict

from metadata_generator.interfaces.diagnostics import Diagnostic


class ArtifactReport(pyd.BaseModel):
    path: str
    status: Literal["create", "update", "skip", "error", "drift"]
    sha256: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorReport(pyd.BaseModel):
    id: str
    status: Literal["ok", "error", "skipped"]
    duration_ms: int
    artifacts: list[ArtifactReport] = pyd.Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineReport(pyd.BaseModel):
    report_version: int = 1
    success: bool
    exit_code: int
    run_id: str
    diagnostics: list[Diagnostic] = pyd.Field(default_factory=list)
    generators: list[GeneratorReport] = pyd.Field(default_factory=list)
    artifacts: list[ArtifactReport] = pyd.Field(default_factory=list)
    timings: dict[str, int] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["ArtifactReport", "EngineReport", "GeneratorReport"]
