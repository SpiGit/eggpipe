"""Тесты реестра форматов и наследования."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

from eggpipe import (
    PRIMITIVE_TYPES,
    Entity,
    EntityModelFormat,
    FormatConflictError,
    FormatRegistry,
    FormatSchema,
    ModelDocument,
    Parser,
    SourceModel,
    UnknownFormatError,
)
from eggpipe.core.model import LayerEntity
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import DocumentError, FormatInheritanceError


class CustomFormat(FormatPlugin):
    format_names: ClassVar[list[str]] = ["custom"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    primitive_types: ClassVar[set[str]] = {"string"}
    schemas: ClassVar[dict[str, FormatSchema]] = {
        "1.0": FormatSchema(layer_entity=Entity, full_entity=Entity)
    }

    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        return ModelDocument(
            format="custom",
            version="1.0",
            path=base_path,
            model=SourceModel(),
        )


class ExtendedEntity(Entity):
    sql_schema: str | None = None


class ExtendedLayer(LayerEntity):
    sql_schema: str | None = None


class ExtendedFormat(EntityModelFormat):
    format_names: ClassVar[list[str]] = ["extended"]
    supported_versions: ClassVar[list[str]] = ["2.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"2.0": "1.0"}
    primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES) | {"decimal"}
    schemas: ClassVar[dict[str, FormatSchema]] = {
        "2.0": FormatSchema(layer_entity=ExtendedLayer, full_entity=ExtendedEntity)
    }


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
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "1.0": FormatSchema(layer_entity=Entity, full_entity=Entity)
        }

        def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
            return EntityModelFormat().parse(raw, base_path)

    with pytest.raises(FormatConflictError):
        registry.register(Reserved())


def test_format_extension_is_valid() -> None:
    registry = FormatRegistry()
    registry.register(ExtendedFormat())
    registry.validate()
    plugin = registry.get("extended")
    assert plugin.supported_versions == ["2.0"]
    assert plugin.schemas["2.0"].full_entity is ExtendedEntity
    assert registry.list()[1].versions == ("2.0",)


def test_schema_keys_must_match_versions() -> None:
    class WrongSchemas(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["wrong"]
        schemas: ClassVar[dict[str, FormatSchema]] = {}

    with pytest.raises(FormatInheritanceError, match="ключи schemas") as caught:
        registry_with(WrongSchemas())
    assert caught.value.code == "MG034"


def test_base_versions_are_required() -> None:
    class MissingBase(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["missing-base"]
        base_versions: ClassVar[dict[str, str]] = {}

    with pytest.raises(FormatInheritanceError, match="base_versions"):
        registry_with(MissingBase())


def test_base_version_must_be_supported() -> None:
    class MissingVersion(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["missing-version"]
        base_versions: ClassVar[dict[str, str]] = {"2.0": "9.9"}

    with pytest.raises(FormatInheritanceError, match="базовая версия"):
        registry_with(MissingVersion())


def test_full_entity_must_extend_base() -> None:
    class NotAnEntity(BaseModel):
        name: str

    class WrongFull(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["wrong-full"]
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "2.0": FormatSchema(layer_entity=ExtendedLayer, full_entity=NotAnEntity)
        }

    with pytest.raises(FormatInheritanceError, match="full_entity"):
        registry_with(WrongFull())


def test_primitive_types_must_include_base() -> None:
    class MissingPrimitives(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["missing-primitives"]
        primitive_types: ClassVar[set[str]] = {"decimal"}

    with pytest.raises(FormatInheritanceError, match="primitive_types"):
        registry_with(MissingPrimitives())


def test_unknown_parent() -> None:
    class UnknownParent(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["unknown-parent"]
        extends: ClassVar[str | None] = "missing"

    with pytest.raises(FormatInheritanceError, match="неизвестный базовый формат"):
        registry_with(UnknownParent())


def test_cycle_is_rejected() -> None:
    class First(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["first"]
        extends: ClassVar[str | None] = "second"

    class Second(ExtendedFormat):
        format_names: ClassVar[list[str]] = ["second"]
        extends: ClassVar[str | None] = "first"

    registry = FormatRegistry()
    registry.register(First())
    registry.register(Second())
    with pytest.raises(FormatInheritanceError, match="цикл"):
        registry.validate()


def test_depth_limit_is_rejected() -> None:
    registry = FormatRegistry()
    parent = "entity-model"
    for index in range(11):
        name = f"level-{index}"
        plugin = type(
            name,
            (EntityModelFormat,),
            {
                "__module__": __name__,
                "format_names": [name],
                "supported_versions": ["1.0"],
                "extends": parent,
                "base_versions": {"1.0": "1.0"},
                "primitive_types": set(PRIMITIVE_TYPES),
                "schemas": {
                    "1.0": FormatSchema(layer_entity=ExtendedLayer, full_entity=ExtendedEntity)
                },
            },
        )
        registry.register(plugin())
        parent = name
    with pytest.raises(FormatInheritanceError, match="глубина"):
        registry.validate()


def test_parser_uses_latest_version(tmp_path: Path) -> None:
    class LatestFormat(EntityModelFormat):
        format_names: ClassVar[list[str]] = ["latest"]
        supported_versions: ClassVar[list[str]] = ["1.0", "2.0"]
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "1.0": FormatSchema(layer_entity=Entity, full_entity=Entity),
            "2.0": FormatSchema(layer_entity=Entity, full_entity=Entity),
        }

    registry = FormatRegistry()
    registry.register(LatestFormat())
    path = tmp_path / "model.yaml"
    path.write_text("format: latest\nmodel: {}\n", encoding="utf-8")
    document = Parser(registry).parse_document(path)
    assert document.version == "2.0"


def test_entity_model_rejects_non_mapping_model(tmp_path: Path) -> None:
    with pytest.raises(DocumentError):
        EntityModelFormat().parse(
            {"format": "entity-model", "version": "1.0", "model": []}, tmp_path
        )


def registry_with(plugin: FormatPlugin) -> FormatRegistry:
    registry = FormatRegistry()
    registry.register(plugin)
    registry.validate()
    return registry


def test_composition_accepts_mixed_root_formats(tmp_path: Path) -> None:
    from eggpipe import Composition

    base = tmp_path / "base.yaml"
    base.write_text(
        'format: entity-model\nversion: "1.0"\nmodel:\n  entities:\n    - name: User\n',
        encoding="utf-8",
    )
    delta = tmp_path / "delta.yaml"
    delta.write_text(
        'format: extended\nversion: "2.0"\nmodel:\n  entities:\n    - name: Post\n',
        encoding="utf-8",
    )
    registry = FormatRegistry()
    registry.register(ExtendedFormat())
    result = Composition(Parser(registry), project_root=tmp_path).resolve([base, delta])
    assert {entity.format for entity in result.model.entities} == {
        "entity-model",
        "extended",
    }


def test_registry_accepts_descendants() -> None:
    registry = FormatRegistry()
    registry.register(ExtendedFormat())
    assert registry.accepts("extended", {"entity-model"}) is True
    assert registry.accepts("extended", {"extended"}) is True
    assert registry.accepts("extended", set()) is False
    assert registry.accepts("extended", None) is True
    assert registry.accepts("missing", {"entity-model"}) is False
