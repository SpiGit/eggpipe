"""Контракты генераторов."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal

import pydantic as pyd
from pydantic import ConfigDict

from metadata_generator.config.generator_rules import GeneratorConfig
from metadata_generator.core.model import ModelSlice
from metadata_generator.core.naming import NamingStyle
from metadata_generator.interfaces.diagnostics import Diagnostic


class ImportedFile(pyd.BaseModel):
    name: str
    path: Path
    content: bytes

    model_config = ConfigDict(extra="forbid", frozen=True)

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding)


class GenerationContext(pyd.BaseModel):
    variables: dict[str, str] = pyd.Field(default_factory=dict)
    naming_hint: NamingStyle | None = None
    imports: dict[str, ImportedFile] = pyd.Field(default_factory=dict)
    sources: list[Path] = pyd.Field(default_factory=list)
    format: str
    format_version: str
    run_id: str
    config_dir: Path

    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(pyd.BaseModel):
    path: str
    content: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationResult(pyd.BaseModel):
    artifacts: list[Artifact] = pyd.Field(default_factory=list)
    warnings: list[Diagnostic] = pyd.Field(default_factory=list)
    errors: list[Diagnostic] = pyd.Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def success(self) -> bool:
        return not self.errors


class GeneratorInput(pyd.BaseModel):
    model: ModelSlice
    config: GeneratorConfig
    context: GenerationContext

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorPlugin(ABC):
    api_version: ClassVar[Literal["1"]] = "1"
    id: ClassVar[str]
    name: ClassVar[str] = ""

    @abstractmethod
    def generate(self, input: GeneratorInput) -> GenerationResult:
        """Сгенерировать артефакты, не записывая файлы."""

    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        return []


__all__ = [
    "Artifact",
    "GenerationContext",
    "GenerationResult",
    "GeneratorInput",
    "GeneratorPlugin",
    "ImportedFile",
]
