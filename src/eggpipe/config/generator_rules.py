"""Бизнес-конфигурация .eggpipe.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from eggpipe.core.model import InputSelection
from eggpipe.core.naming import NamingStyle
from eggpipe.utils.exceptions import ConfigValidationError
from eggpipe.utils.yaml import YamlLoadError, load_yaml

Layout = Literal["monolith", "file-per-model", "directory-per-model"]


class ResourceConfig(BaseModel):
    path: Path
    as_: str | None = Field(default=None, alias="as")

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    @property
    def alias(self) -> str | None:
        return self.as_


def _coerce_resource(value: object) -> object:
    if isinstance(value, str):
        return {"path": value}
    return value


ResourceInput = Annotated[ResourceConfig, BeforeValidator(_coerce_resource)]


class InputSlice(InputSelection):
    """Совместимое имя выбора input из System Design."""


class ModelOverride(BaseModel):
    files: tuple[str, ...] | None = None
    resources: tuple[ResourceInput, ...] | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorConfig(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    enabled: bool = True
    input: InputSlice = Field(default_factory=InputSlice)
    output_dir: Path
    on_conflict: Literal["overwrite", "skip", "error"] = "overwrite"
    cleanup: Literal["off", "prompt", "enabled"] = "off"
    options: dict[str, object] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("output_dir")
    @classmethod
    def _output_dir_must_be_relative(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError("output_dir должен быть относительным")
        return value


class DefaultsConfig(BaseModel):
    naming_convention: NamingStyle | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceConfig(BaseModel):
    path: Path
    layout: Layout
    files: tuple[str, ...] | None = None
    model_dirs: tuple[str, ...] | None = None
    models: dict[str, ModelOverride] = Field(default_factory=dict)
    input: InputSlice = Field(default_factory=InputSlice)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _validate_layout(self) -> SourceConfig:
        if self.layout == "monolith":
            if self.files is not None or self.model_dirs is not None or self.models:
                raise ValueError("monolith не поддерживает files/model_dirs/models")
            return self
        if not self.files:
            raise ValueError(f"{self.layout} требует непустой files")
        if self.layout == "file-per-model":
            if self.model_dirs is not None or self.models:
                raise ValueError("file-per-model не поддерживает model_dirs/models")
            return self
        if not self.model_dirs:
            raise ValueError("directory-per-model требует непустой model_dirs")
        return self


class DiagnosticsConfig(BaseModel):
    stale_dates: bool = False
    ignore: frozenset[str] = frozenset()

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorRules(BaseModel):
    version: Literal["1.0"]
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    diagnostics: DiagnosticsConfig = Field(default_factory=DiagnosticsConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    resources: tuple[ResourceInput, ...] = ()
    sources: tuple[SourceConfig, ...] = ()
    generators: tuple[GeneratorConfig, ...] = ()

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorRulesLoader:
    """Загрузка и поиск .eggpipe.yaml."""

    def load(self, path: Path) -> GeneratorRules:
        try:
            data = load_yaml(path)
        except YamlLoadError as exc:
            raise ConfigValidationError(f"{path}: {exc.code}: {exc.message}") from exc
        try:
            return GeneratorRules.model_validate(data)
        except ValidationError as exc:
            raise ConfigValidationError(f"{path}: {exc}") from exc

    @classmethod
    def discover(cls, start: Path | None = None) -> Path | None:
        current = (start or Path.cwd()).resolve()
        for directory in (current, *current.parents):
            for name in (".eggpipe.yaml",):
                candidate = directory / name
                if candidate.is_file():
                    return candidate
        return None


__all__ = [
    "DefaultsConfig",
    "DiagnosticsConfig",
    "GeneratorConfig",
    "GeneratorRules",
    "GeneratorRulesLoader",
    "InputSlice",
    "Layout",
    "ModelOverride",
    "ResourceConfig",
    "SourceConfig",
]
