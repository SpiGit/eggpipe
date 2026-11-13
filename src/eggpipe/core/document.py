"""Model document and imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from eggpipe.core.model import SourceModel


class ImportSpec(BaseModel):
    path: str
    alias: str | None = None
    kind: Literal["yaml", "resource"]

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelDocument(BaseModel):
    format: str
    version: str
    path: Path
    imports: tuple[ImportSpec, ...] = ()
    model: SourceModel
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["ImportSpec", "ModelDocument"]
