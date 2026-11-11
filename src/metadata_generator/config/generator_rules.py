"""Бизнес-конфигурация .mg.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pydantic as pyd
from pydantic import ConfigDict, field_validator

from metadata_generator.core.model import InputSelection
from metadata_generator.core.naming import NamingStyle
from metadata_generator.utils.exceptions import ConfigValidationError
from metadata_generator.utils.yaml import YamlLoadError, load_yaml


class InputSlice(InputSelection):
    """Совместимое имя выбора input из System Design."""


class GeneratorConfig(pyd.BaseModel):
    id: str = pyd.Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    enabled: bool = True
    input: InputSlice = pyd.Field(default_factory=InputSlice)
    output_dir: Path
    on_conflict: Literal["overwrite", "skip", "error"] = "overwrite"
    cleanup: Literal["off", "prompt", "enabled"] = "off"
    options: dict[str, object] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("output_dir")
    @classmethod
    def _output_dir_must_be_relative(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError("output_dir должен быть относительным")
        return value


class DefaultsConfig(pyd.BaseModel):
    naming_convention: NamingStyle | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceConfig(pyd.BaseModel):
    path: Path
    input: InputSlice = pyd.Field(default_factory=InputSlice)

    model_config = ConfigDict(extra="forbid", frozen=True)


class DiagnosticsConfig(pyd.BaseModel):
    stale_dates: bool = False
    ignore: frozenset[str] = frozenset()

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorRules(pyd.BaseModel):
    version: Literal["1.0"]
    defaults: DefaultsConfig = pyd.Field(default_factory=DefaultsConfig)
    diagnostics: DiagnosticsConfig = pyd.Field(default_factory=DiagnosticsConfig)
    variables: dict[str, str] = pyd.Field(default_factory=dict)
    sources: tuple[SourceConfig, ...] = ()
    generators: tuple[GeneratorConfig, ...] = ()

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorRulesLoader:
    """Загрузка и поиск .mg.yaml."""

    def load(self, path: Path) -> GeneratorRules:
        try:
            data = load_yaml(path)
        except YamlLoadError as exc:
            raise ConfigValidationError(f"{path}: {exc.code}: {exc.message}") from exc
        try:
            return GeneratorRules.model_validate(data)
        except pyd.ValidationError as exc:
            raise ConfigValidationError(f"{path}: {exc}") from exc

    @classmethod
    def discover(cls, start: Path | None = None) -> Path | None:
        current = (start or Path.cwd()).resolve()
        for directory in (current, *current.parents):
            for name in (".mg.yaml", ".mg.yml"):
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
    "SourceConfig",
]
