"""Тесты реестра форматов."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from eggpipe import (
    EntityModelFormat,
    FormatConflictError,
    FormatRegistry,
    ModelDocument,
    SourceModel,
    UnknownFormatError,
)
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import DocumentError


class CustomFormat(FormatPlugin):
    format_names: ClassVar[list[str]] = ["custom"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    primitive_types: ClassVar[set[str]] = {"string"}

    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        return ModelDocument(
            format="custom",
            version="1.0",
            path=base_path,
            model=SourceModel(),
        )


def test_default_registry_contains_entity_model() -> None:
    registry = FormatRegistry()
    assert registry.get("entity-model").format_names == ["entity-model"]
    assert [item.name for item in registry.list()] == ["entity-model"]


def test_unknown_format() -> None:
    with pytest.raises(UnknownFormatError):
        FormatRegistry().get("missing")


def test_duplicate_and_reserved_formats() -> None:
    registry = FormatRegistry()
    with pytest.raises(FormatConflictError):
        registry.register(CustomFormat())
        registry.register(CustomFormat())

    class Reserved(FormatPlugin):
        format_names: ClassVar[list[str]] = ["entity-model"]
        supported_versions: ClassVar[list[str]] = ["1.0"]
        primitive_types: ClassVar[set[str]] = set()

        def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
            return EntityModelFormat().parse(raw, base_path)

    with pytest.raises(FormatConflictError):
        registry.register(Reserved())


def test_entity_model_rejects_non_mapping_model(tmp_path: Path) -> None:
    with pytest.raises(DocumentError):
        EntityModelFormat().parse(
            {"format": "entity-model", "version": "1.0", "model": []}, tmp_path
        )
