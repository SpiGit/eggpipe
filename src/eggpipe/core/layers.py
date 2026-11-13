"""Сборка model unit из слоёв форматов (ADR-0008)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import CustomType, Entity, EnumDef, FieldDef, SourceModel
from eggpipe.interfaces.diagnostics import Diagnostic, warning
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import DocumentError


class FormatLookup(Protocol):
    def get(self, name: str) -> FormatPlugin: ...


@dataclass(frozen=True)
class LayerMergeResult:
    document: ModelDocument
    diagnostics: list[Diagnostic]


def merge_model_layers(
    documents: list[ModelDocument],
    registry: FormatLookup,
) -> LayerMergeResult:
    """Проверить и аддитивно смержить слои одной модели."""
    if not documents:
        raise DocumentError("MG027", None, "пустая модель")
    layers = _ordered_layers(documents, registry)
    diagnostics: list[Diagnostic] = []

    base_doc = layers[0]
    base_plugin = registry.get(base_doc.format)
    _validate_entity(
        base_plugin,
        base_doc,
        "full_entity",
        _entity(base_doc),
    )

    merged = _entity(base_doc)
    enums = list(base_doc.model.enums)
    types = list(base_doc.model.types)
    metadata = dict(base_doc.model.metadata)
    document_metadata = dict(base_doc.metadata)
    layer_sources = [base_doc.path]

    for index, delta_doc in enumerate(layers[1:], start=1):
        delta_plugin = registry.get(delta_doc.format)
        _validate_layer_chain(layers[index - 1], delta_doc, delta_plugin)
        _validate_entity(delta_plugin, delta_doc, "layer_entity", _entity(delta_doc))

        delta = _entity(delta_doc)
        if delta.name != merged.name:
            raise DocumentError(
                "MG029",
                delta_doc.path,
                f"слой {delta_doc.format} описывает {delta.name}, ожидался {merged.name}",
            )
        added = False
        merged, merged_added = _merge_entity(merged, delta, delta_doc.path)
        added |= merged_added
        enums, enums_added = _merge_enums(enums, delta_doc.model.enums, delta_doc.path)
        added |= enums_added
        types, types_added = _merge_types(types, delta_doc.model.types, delta_doc.path)
        added |= types_added
        metadata, metadata_added = _merge_metadata(
            metadata,
            delta_doc.model.metadata,
            delta_doc.path,
        )
        added |= metadata_added
        document_metadata, doc_added = _merge_metadata(
            document_metadata, delta_doc.metadata, delta_doc.path
        )
        added |= doc_added
        layer_sources.append(delta_doc.path)
        if not added:
            diagnostics.append(
                warning(
                    "MG035",
                    f"дельта {delta_doc.format} не добавляет ничего",
                    path=str(delta_doc.path),
                )
            )

    derived_doc = layers[-1]
    derived_plugin = registry.get(derived_doc.format)
    final = merged.model_copy(
        update={
            "format": derived_doc.format,
            "format_version": derived_doc.version,
            "layer_sources": tuple(layer_sources),
        }
    )
    _validate_entity(derived_plugin, derived_doc, "full_entity", final)
    model = SourceModel(
        name=base_doc.model.name,
        description=base_doc.model.description,
        entities=(final,),
        enums=tuple(enums),
        types=tuple(types),
        metadata=metadata,
    )
    document = ModelDocument(
        format=derived_doc.format,
        version=derived_doc.version,
        path=base_doc.path,
        imports=(),
        model=model,
        metadata=document_metadata,
    )
    return LayerMergeResult(document=document, diagnostics=diagnostics)


def _ordered_layers(
    documents: list[ModelDocument],
    registry: FormatLookup,
) -> list[ModelDocument]:
    by_format: dict[str, ModelDocument] = {}
    plugins: dict[str, FormatPlugin] = {}
    for document in documents:
        if len(document.model.entities) != 1:
            raise DocumentError("MG031", document.path, "файл-слой должен содержать одну сущность")
        if document.imports:
            raise DocumentError("MG029", document.path, "imports в файле-слое запрещены")
        entity = document.model.entities[0]
        if entity.extends is not None:
            raise DocumentError("MG029", document.path, "extends в файле-слое запрещён")
        if document.format in by_format:
            raise DocumentError(
                "MG029",
                document.path,
                f"несколько файлов одного формата: {document.format}",
            )
        by_format[document.format] = document
        plugins[document.format] = registry.get(document.format)

    roots = [
        name
        for name, plugin in plugins.items()
        if plugin.extends is None or plugin.extends not in plugins
    ]
    if len(roots) != 1:
        raise DocumentError("MG029", documents[0].path, "форматы слоёв не образуют одну цепочку")

    ordered = [roots[0]]
    current = roots[0]
    while True:
        children = [name for name, plugin in plugins.items() if plugin.extends == current]
        if len(children) > 1:
            raise DocumentError(
                "MG029",
                documents[0].path,
                "форматы слоёв образуют ветвление",
            )
        if not children:
            break
        ordered.append(children[0])
        current = children[0]
    if set(ordered) != set(by_format):
        raise DocumentError("MG029", documents[0].path, "форматы слоёв не связаны наследованием")
    return [by_format[name] for name in ordered]


def _validate_layer_chain(
    parent: ModelDocument,
    child: ModelDocument,
    child_plugin: FormatPlugin,
) -> None:
    expected = child_plugin.base_versions.get(child.version)
    if expected is None:
        raise DocumentError(
            "MG034",
            child.path,
            f"{child.format} {child.version}: нет base_versions",
        )
    if expected != parent.version:
        raise DocumentError(
            "MG034",
            child.path,
            f"{child.format} {child.version} требует {parent.format} {expected}, "
            f"а слой имеет {parent.version}",
        )


def _validate_entity(
    plugin: FormatPlugin,
    document: ModelDocument,
    schema_name: str,
    entity: Entity,
) -> None:
    schema = plugin.schemas.get(document.version)
    if schema is None:
        raise DocumentError(
            "MG034",
            document.path,
            f"{document.format} {document.version}: нет схемы",
        )
    model: type[BaseModel] = getattr(schema, schema_name)
    try:
        model.model_validate(entity.model_dump())
    except ValidationError as exc:
        raise DocumentError(
            "MG029",
            document.path,
            f"{document.format} {document.version}: {schema_name}: {exc}",
        ) from exc


def _entity(document: ModelDocument) -> Entity:
    return document.model.entities[0]


def _merge_entity(
    base: Entity,
    delta: Entity,
    source: Path,
) -> tuple[Entity, bool]:
    added = False
    values: dict[str, Any] = {}
    for name in ("description", "version", "updated_at"):
        left = getattr(base, name)
        right = getattr(delta, name)
        if right is None:
            continue
        if left is None:
            values[name] = right
            added = True
        elif left != right:
            raise DocumentError(
                "MG029",
                source,
                f"конфликт scalar {name}: {left!r} и {right!r}",
            )
    metadata, metadata_added = _merge_metadata(base.metadata, delta.metadata, source)
    if metadata_added:
        values["metadata"] = metadata
        added = True

    fields = list(base.fields)
    by_name = {field.name: index for index, field in enumerate(fields)}
    for field in delta.fields:
        index = by_name.get(field.name)
        if index is None:
            fields.append(field.model_copy(update={"source": source}))
            by_name[field.name] = len(fields) - 1
            added = True
            continue
        fields[index], field_added = _merge_field(fields[index], field, source)
        added |= field_added
    if added or len(fields) != len(base.fields):
        values["fields"] = tuple(fields)
    return base.model_copy(update=values), added


def _merge_field(base: FieldDef, delta: FieldDef, source: Path) -> tuple[FieldDef, bool]:
    left = base.model_dump(exclude={"metadata"})
    right = delta.model_dump(exclude={"metadata"})
    if left != right:
        raise DocumentError(
            "MG029",
            source,
            f"переопределение поля {base.name} запрещено",
        )
    metadata, added = _merge_metadata(base.metadata, delta.metadata, source)
    if not added:
        return base, False
    return base.model_copy(update={"metadata": metadata}), True


def _merge_enums(
    base: list[EnumDef],
    delta: tuple[EnumDef, ...],
    source: Path,
) -> tuple[list[EnumDef], bool]:
    result = list(base)
    by_name = {item.name: item for item in result}
    added = False
    for item in delta:
        existing = by_name.get(item.name)
        if existing is None:
            result.append(item)
            by_name[item.name] = item
            added = True
            continue
        if existing != item:
            raise DocumentError("MG029", source, f"переопределение enum {item.name} запрещено")
    return result, added


def _merge_types(
    base: list[CustomType],
    delta: tuple[CustomType, ...],
    source: Path,
) -> tuple[list[CustomType], bool]:
    result = list(base)
    by_name = {item.name: item for item in result}
    added = False
    for item in delta:
        existing = by_name.get(item.name)
        if existing is None:
            result.append(item)
            by_name[item.name] = item
            added = True
            continue
        if existing != item:
            raise DocumentError("MG029", source, f"переопределение type {item.name} запрещено")
    return result, added


def _merge_metadata(
    base: dict[str, Any],
    delta: dict[str, Any],
    source: Path,
) -> tuple[dict[str, Any], bool]:
    result = dict(base)
    changed = False
    for key, value in delta.items():
        if key not in result:
            result[key] = value
            changed = True
            continue
        current = result[key]
        if isinstance(current, dict) and isinstance(value, dict):
            merged, nested = _merge_metadata(current, value, source)
            if nested:
                result[key] = merged
                changed = True
            continue
        if isinstance(current, list) and isinstance(value, list):
            if value:
                result[key] = [*current, *value]
                changed = True
            continue
        if current != value:
            raise DocumentError(
                "MG029",
                source,
                f"конфликт metadata.{key}: {current!r} и {value!r}",
            )
    return result, changed


__all__ = ["FormatLookup", "LayerMergeResult", "merge_model_layers"]
