"""Модель отчёта Engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eggpipe.interfaces.diagnostics import Diagnostic


class FormatReport(BaseModel):
    name: str
    version: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class FormatSummary(FormatReport):
    entities: int = 0


class ArtifactReport(BaseModel):
    generator: str = ""
    path: str
    action: Literal["create", "update", "skip", "delete", "conflict", "error", "drift"]
    sha256: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorReport(BaseModel):
    id: str
    name: str = ""
    status: Literal["ok", "error", "skipped"]
    input_formats: list[str] | None = None
    formats: list[FormatReport] = Field(default_factory=list)
    duration_ms: int

    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestLocationSummary(BaseModel):
    generator: str
    output_dir: str
    artifacts: int

    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestSummary(BaseModel):
    manifest_version: int
    locations: list[ManifestLocationSummary] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


class StaleLocation(BaseModel):
    generator: str
    output_dir: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineReport(BaseModel):
    report_version: int = 2
    success: bool
    exit_code: int
    run_id: str
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    formats: list[FormatSummary] = Field(default_factory=list)
    generators: list[GeneratorReport] = Field(default_factory=list)
    artifacts: list[ArtifactReport] = Field(default_factory=list)
    manifest: ManifestSummary | None = None
    stale_locations: list[StaleLocation] = Field(default_factory=list)
    timings: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = [
    "ArtifactReport",
    "EngineReport",
    "FormatReport",
    "FormatSummary",
    "GeneratorReport",
    "ManifestLocationSummary",
    "ManifestSummary",
    "StaleLocation",
]
