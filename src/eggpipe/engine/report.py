"""Модель отчёта Engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eggpipe.interfaces.diagnostics import Diagnostic


class ArtifactReport(BaseModel):
    path: str
    status: Literal["create", "update", "skip", "error", "drift"]
    sha256: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorReport(BaseModel):
    id: str
    status: Literal["ok", "error", "skipped"]
    duration_ms: int
    artifacts: list[ArtifactReport] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineReport(BaseModel):
    report_version: int = 1
    success: bool
    exit_code: int
    run_id: str
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    generators: list[GeneratorReport] = Field(default_factory=list)
    artifacts: list[ArtifactReport] = Field(default_factory=list)
    timings: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["ArtifactReport", "EngineReport", "GeneratorReport"]
