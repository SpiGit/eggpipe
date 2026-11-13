"""Build a model unit from format layers (ADR-0008)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import CustomType, Entity, EnumDef, FieldDef, SourceModel
from eggpipe.interfaces.diagnostics import Diagnostic, warning
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import DocumentError


class FormatLookup(Protocol):
    def get(self, name: str) -> FormatPlugin: ...


T = TypeVar("T")


@dataclass(frozen=True)
class MergeChange(Generic[T]):
    value: T
    changed: bool = False


_MISSING = object()


@dataclass(frozen=True)
class LayerMergeResult:
    document: ModelDocument
    diagnostics: list[Diagnostic]


def merge_model_layers(
    documents: list[ModelDocument],
    registry: FormatLookup,
) -> LayerMergeResult:
    """Validate and additively merge the layers of one model."""
    if not documents:
        raise DocumentError("EG027", None, "empty model")
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
                "EG029",
                delta_doc.path,
                f"layer {delta_doc.format} describes {delta.name}, expected {merged.name}",
            )
        merged_change = _merge_entity(merged, delta, delta_doc.path)
        enums_change = _merge_enums(enums, delta_doc.model.enums, delta_doc.path)
        types_change = _merge_types(types, delta_doc.model.types, delta_doc.path)
        metadata_change = _merge_metadata(
            metadata,
            delta_doc.model.metadata,
            delta_doc.path,
        )
        document_metadata_change = _merge_metadata(
            document_metadata,
            delta_doc.metadata,
            delta_doc.path,
            path="document.metadata",
        )
        merged = merged_change.value
        enums = enums_change.value
        types = types_change.value
        metadata = metadata_change.value
        document_metadata = document_metadata_change.value
        added = any(
            change.changed
            for change in (
                merged_change,
                enums_change,
                types_change,
                metadata_change,
                document_metadata_change,
            )
        )
        layer_sources.append(delta_doc.path)
        if not added:
            diagnostics.append(
                warning(
                    "EG035",
                    f"delta {delta_doc.format} adds nothing",
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
            raise DocumentError(
                "EG031", document.path, "a layer file must contain exactly one entity"
            )
        if document.imports:
            raise DocumentError("EG029", document.path, "imports are not allowed in a layer file")
        entity = document.model.entities[0]
        if entity.extends is not None:
            raise DocumentError("EG029", document.path, "extends is not allowed in a layer file")
        if document.format in by_format:
            raise DocumentError(
                "EG029",
                document.path,
                f"multiple files of the same format: {document.format}",
            )
        by_format[document.format] = document
        plugins[document.format] = registry.get(document.format)

    roots = [
        name
        for name, plugin in plugins.items()
        if plugin.extends is None or plugin.extends not in plugins
    ]
    if len(roots) != 1:
        raise DocumentError("EG029", documents[0].path, "layer formats do not form a single chain")

    ordered = [roots[0]]
    current = roots[0]
    while True:
        children = [name for name, plugin in plugins.items() if plugin.extends == current]
        if len(children) > 1:
            raise DocumentError(
                "EG029",
                documents[0].path,
                "layer formats form a branch",
            )
        if not children:
            break
        ordered.append(children[0])
        current = children[0]
    if set(ordered) != set(by_format):
        raise DocumentError(
            "EG029", documents[0].path, "layer formats are not connected by inheritance"
        )
    return [by_format[name] for name in ordered]


def _validate_layer_chain(
    parent: ModelDocument,
    child: ModelDocument,
    child_plugin: FormatPlugin,
) -> None:
    expected = child_plugin.base_versions.get(child.version)
    if expected is None:
        raise DocumentError(
            "EG034",
            child.path,
            f"{child.format} {child.version}: base_versions is missing",
        )
    if expected != parent.version:
        raise DocumentError(
            "EG034",
            child.path,
            f"{child.format} {child.version} requires {parent.format} {expected}, "
            f"but the layer has {parent.version}",
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
            "EG034",
            document.path,
            f"{document.format} {document.version}: schema is missing",
        )
    model: type[BaseModel] = getattr(schema, schema_name)
    try:
        model.model_validate(entity, from_attributes=True)
    except ValidationError as exc:
        raise DocumentError(
            "EG029",
            document.path,
            f"{document.format} {document.version}: {schema_name}: {exc}",
        ) from exc


def _entity(document: ModelDocument) -> Entity:
    return document.model.entities[0]


def _merge_entity(
    base: Entity,
    delta: Entity,
    source: Path,
) -> MergeChange[Entity]:
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
                "EG029",
                source,
                f"scalar conflict for {name}: {left!r} and {right!r}",
            )
    metadata_change = _merge_metadata(base.metadata, delta.metadata, source)
    if metadata_change.changed:
        values["metadata"] = metadata_change.value
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
        field_change = _merge_field(fields[index], field, source)
        fields[index] = field_change.value
        added |= field_change.changed
    if added or len(fields) != len(base.fields):
        values["fields"] = tuple(fields)
    return MergeChange(base.model_copy(update=values), added)


def _merge_field(base: FieldDef, delta: FieldDef, source: Path) -> MergeChange[FieldDef]:
    left = base.model_dump(exclude={"metadata"})
    right = delta.model_dump(exclude={"metadata"})
    if left != right:
        raise DocumentError(
            "EG029",
            source,
            f"overriding field {base.name} is not allowed",
        )
    metadata_change = _merge_metadata(base.metadata, delta.metadata, source)
    if not metadata_change.changed:
        return MergeChange(base)
    return MergeChange(
        base.model_copy(update={"metadata": metadata_change.value}),
        True,
    )


def _merge_enums(
    base: list[EnumDef],
    delta: tuple[EnumDef, ...],
    source: Path,
) -> MergeChange[list[EnumDef]]:
    return _merge_append(base, delta, source, label="enum", key=lambda item: item.name)


def _merge_types(
    base: list[CustomType],
    delta: tuple[CustomType, ...],
    source: Path,
) -> MergeChange[list[CustomType]]:
    return _merge_append(base, delta, source, label="type", key=lambda item: item.name)


def _merge_append(
    base: list[T],
    delta: tuple[T, ...],
    source: Path,
    *,
    label: str,
    key: Callable[[T], str],
) -> MergeChange[list[T]]:
    by_name = {key(item): item for item in base}
    result = list(base)
    added = False
    for item in delta:
        name = key(item)
        existing = by_name.get(name)
        if existing is None:
            result.append(item)
            by_name[name] = item
            added = True
        elif existing != item:
            raise DocumentError("EG029", source, f"overriding {label} {name} is not allowed")
    return MergeChange(result, added)


def _merge_metadata(
    base: dict[str, Any],
    delta: dict[str, Any],
    source: Path,
    *,
    path: str = "metadata",
) -> MergeChange[dict[str, Any]]:
    result = dict(base)
    changed = False
    for key, value in delta.items():
        change = _merge_value(result.get(key, _MISSING), value, source, f"{path}.{key}")
        if change.changed:
            result[key] = change.value
            changed = True
    return MergeChange(result, changed)


def _merge_value(current: Any, incoming: Any, source: Path, path: str) -> MergeChange[Any]:
    if current is _MISSING:
        return MergeChange(incoming, True)
    match current, incoming:
        case dict(), dict():
            return _merge_metadata(current, incoming, source, path=path)
        case list(), list():
            return MergeChange([*current, *incoming], bool(incoming))
        case _ if current == incoming:
            return MergeChange(current)
        case _:
            raise DocumentError(
                "EG029",
                source,
                f"conflict at {path}: {current!r} and {incoming!r}",
            )


__all__ = ["FormatLookup", "LayerMergeResult", "merge_model_layers"]
