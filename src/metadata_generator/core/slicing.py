"""Формирование замкнутого среза модели."""

from __future__ import annotations

from collections.abc import Iterable

from metadata_generator.core.model import (
    Entity,
    InputSelection,
    ModelSlice,
    SourceModel,
)
from metadata_generator.interfaces.diagnostics import Diagnostic, error


def select_slice(
    model: SourceModel,
    selection: InputSelection | None = None,
) -> tuple[ModelSlice, list[Diagnostic]]:
    """Выбрать подмножество и добавить транзитивное замыкание по enums/types."""
    if selection is None:
        return (
            ModelSlice(
                entities=model.entities,
                enums=model.enums,
                types=model.types,
            ),
            [],
        )

    diagnostics: list[Diagnostic] = []
    entity_names = _requested(
        "entities",
        [item.name for item in model.entities],
        selection.entities,
        diagnostics,
    )
    enum_names = _requested(
        "enums",
        [item.name for item in model.enums],
        selection.enums,
        diagnostics,
    )
    type_names = _requested(
        "types",
        [item.name for item in model.types],
        selection.types,
        diagnostics,
    )

    entities = tuple(
        item for item in model.entities if entity_names is None or item.name in entity_names
    )
    enum_map = {item.name: item for item in model.enums}
    type_map = {item.name: item for item in model.types}

    selected_enums = {item.name for item in model.enums} if enum_names is None else set(enum_names)
    selected_types = {item.name for item in model.types} if type_names is None else set(type_names)

    changed = True
    while changed:
        changed = False
        for name in _referenced(entities, model, selected_types):
            if name in enum_map and name not in selected_enums:
                selected_enums.add(name)
                changed = True
            elif name in type_map and name not in selected_types:
                selected_types.add(name)
                changed = True

    enums = tuple(item for item in model.enums if item.name in selected_enums)
    types = tuple(item for item in model.types if item.name in selected_types)
    return ModelSlice(entities=entities, enums=enums, types=types), diagnostics


def _requested(
    label: str,
    available: list[str],
    requested: tuple[str, ...] | None,
    diagnostics: list[Diagnostic],
) -> set[str] | None:
    if not requested:
        return None
    available_set = set(available)
    for name in requested:
        if name not in available_set:
            diagnostics.append(
                error("MG018", f"неизвестное имя в input.{label}: {name}", path=f"input.{label}")
            )
    return set(requested)


def _referenced(
    entities: Iterable[Entity],
    model: SourceModel,
    selected_types: set[str],
) -> set[str]:
    names: set[str] = set()
    for entity in entities:
        for field in entity.fields:
            names.add(field.type)
    type_map = {item.name: item for item in model.types}
    for name in tuple(selected_types):
        custom = type_map.get(name)
        if custom is not None:
            names.add(custom.base)
    return names


__all__ = ["select_slice"]
