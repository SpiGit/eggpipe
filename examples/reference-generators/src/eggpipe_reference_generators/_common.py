"""Shared helpers for the reference generators."""

from __future__ import annotations

from eggpipe import PRIMITIVE_TYPES, Entity, ModelSlice, NamingStyle, transform

_MAX_TYPE_DEPTH = 8


def sorted_entities(model: ModelSlice) -> tuple[Entity, ...]:
    """Return entities in a stable order: by name."""
    return tuple(sorted(model.entities, key=lambda entity: entity.name))


def snake_case(name: str) -> str:
    return transform(name, NamingStyle.SNAKE)


def camel_case(name: str) -> str:
    return transform(name, NamingStyle.CAMEL)


def pascal_case(name: str) -> str:
    return transform(name, NamingStyle.PASCAL)


def primitive_type(field_type: str, model: ModelSlice) -> str:
    """Reduce a field type to a primitive, unwrapping custom types.

    Enums and unknown types map to `string`: the example intentionally does not
    emit enum types and relies on the string representation.
    """
    bases = {custom.name: custom.base for custom in model.types}
    current = field_type
    for _ in range(_MAX_TYPE_DEPTH):
        if current in PRIMITIVE_TYPES:
            return current
        base = bases.get(current)
        if base is None:
            break
        current = base
    return "string"
