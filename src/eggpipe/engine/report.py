"""Engine report model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class CacheMissReasons(BaseModel):
    changed: int = Field(default=0, ge=0)
    missing: int = Field(default=0, ge=0)
    invalid: int = Field(default=0, ge=0)
    version: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CacheReport(BaseModel):
    """Per-run L2 cache metrics (ADR-0021)."""

    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    miss_reasons: CacheMissReasons
    entries: int = Field(ge=0)
    bytes: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _reasons_match_misses(self) -> CacheReport:
        reasons = self.miss_reasons
        total = reasons.changed + reasons.missing + reasons.invalid + reasons.version
        if total != self.misses:
            raise ValueError("cache miss reasons must sum to misses")
        return self


class StaleLocation(BaseModel):
    generator: str
    output_dir: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineReport(BaseModel):
    report_version: int = 3
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
    cache: CacheReport | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = [
    "ArtifactReport",
    "CacheMissReasons",
    "CacheReport",
    "EngineReport",
    "FormatReport",
    "FormatSummary",
    "GeneratorReport",
    "ManifestLocationSummary",
    "ManifestSummary",
    "StaleLocation",
]
