"""Документ модели и импорты."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pydantic as pyd
from pydantic import ConfigDict

from metadata_generator.core.model import SourceModel


class ImportSpec(pyd.BaseModel):
    path: str
    alias: str | None = None
    kind: Literal["yaml", "resource"]

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelDocument(pyd.BaseModel):
    format: str
    version: str
    path: Path
    imports: tuple[ImportSpec, ...] = ()
    model: SourceModel
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["ImportSpec", "ModelDocument"]
