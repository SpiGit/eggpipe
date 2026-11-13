"""Контракты генераторов."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from eggpipe.config.generator_rules import GeneratorConfig
from eggpipe.core.model import FormatInfo, ModelSlice
from eggpipe.core.naming import NamingStyle
from eggpipe.interfaces.diagnostics import Diagnostic


class ImportedFile(BaseModel):
    name: str
    path: Path
    content: bytes

    model_config = ConfigDict(extra="forbid", frozen=True)

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding)


class GenerationContext(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)
    naming_hint: NamingStyle | None = None
    imports: dict[str, ImportedFile] = Field(default_factory=dict)
    sources: list[Path] = Field(default_factory=list)
    formats: frozenset[FormatInfo] = frozenset()
    run_id: str
    config_dir: Path

    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(BaseModel):
    path: str
    content: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationResult(BaseModel):
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[Diagnostic] = Field(default_factory=list)
    errors: list[Diagnostic] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def success(self) -> bool:
        return not self.errors


class GeneratorInput(BaseModel):
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
