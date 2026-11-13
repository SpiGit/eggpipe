"""Парсер документов модели."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import SourceModel
from eggpipe.engine.format_registry import FormatRegistry
from eggpipe.utils.exceptions import (
    DocumentError,
    UnknownFormatError,
)
from eggpipe.utils.yaml import YamlLoadError, load_yaml


def normalize_version(value: object) -> str | None:
    """Нормализовать version: строка как есть, число — в строку с одним знаком."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return f"{value}.0"
    if isinstance(value, float):
        return f"{value:.1f}"
    return None


class Parser:
    def __init__(self, registry: FormatRegistry | None = None) -> None:
        self.registry = registry or FormatRegistry()

    def parse_document(self, path: Path) -> ModelDocument:
        try:
            raw = load_yaml(path)
        except YamlLoadError as exc:
            raise DocumentError(exc.code, path, exc.message) from exc

        format_name = raw.get("format")
        if not isinstance(format_name, str) or not format_name:
            raise DocumentError("MG007", path, "`format` обязателен")

        try:
            plugin = self.registry.get(format_name)
        except UnknownFormatError as exc:
            raise DocumentError("MG007", path, str(exc)) from exc

        raw_version = raw.get("version")
        if raw_version is None:
            version = plugin.supported_versions[-1]
        else:
            version = normalize_version(raw_version)
            if version is None:
                raise DocumentError("MG008", path, "`version` должен быть строкой или числом")
            if version not in plugin.supported_versions:
                raise DocumentError(
                    "MG008",
                    path,
                    f"{format_name} не поддерживает версию {version}",
                )

        raw["format"] = format_name
        raw["version"] = version
        try:
            document = plugin.parse(raw, base_path=path.parent)
        except DocumentError:
            raise
        except ValidationError as exc:
            raise DocumentError("MG028", path, str(exc)) from exc
        model = SourceModel(
            name=document.model.name,
            description=document.model.description,
            metadata=document.model.metadata,
            entities=tuple(
                entity.model_copy(
                    update={
                        "source": path,
                        "format": format_name,
                        "format_version": version,
                        "fields": tuple(
                            field.model_copy(update={"source": path}) for field in entity.fields
                        ),
                    }
                )
                for entity in document.model.entities
            ),
            enums=document.model.enums,
            types=document.model.types,
        )
        return document.model_copy(update={"path": path, "model": model})


__all__ = ["Parser", "normalize_version"]
