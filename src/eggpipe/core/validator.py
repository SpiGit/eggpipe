"""Семантическая валидация модели поверх Pydantic."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import (
    PRIMITIVE_TYPES,
    UNSET,
    Constraints,
    CustomType,
    Entity,
    EnumDef,
    FieldDef,
    ModelSlice,
    SourceModel,
)
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning

MAX_TYPE_DEPTH = 10
MAX_IMPORT_DEPTH = 10


def validate_entity_model(
    model: SourceModel | ModelSlice,
    *,
    primitive_types: set[str] | frozenset[str] | None = None,
    file: Path | None = None,
) -> list[Diagnostic]:
    primitives = set(primitive_types or PRIMITIVE_TYPES)
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_duplicate_names(model, file))
    diagnostics.extend(_validate_case_collisions(model, file))

    type_bases = _resolve_type_bases(model, primitives, file, diagnostics)

    for enum in model.enums:
        diagnostics.extend(_validate_enum(enum, file))

    referenced: set[str] = set()
    for entity in model.entities:
        diagnostics.extend(
            _validate_entity(entity, model, primitives, type_bases, referenced, file)
        )

    for custom_type in model.types:
        referenced.add(custom_type.base)
    for enum in model.enums:
        if enum.name not in referenced:
            diagnostics.append(
                warning(
                    "MG013",
                    f"enum {enum.name} не используется",
                    file=file,
                    entity=enum.name,
                )
            )
    for custom_type in model.types:
        if custom_type.name not in referenced:
            diagnostics.append(
                warning(
                    "MG013",
                    f"type {custom_type.name} не используется",
                    file=file,
                    entity=custom_type.name,
                )
            )
    return diagnostics


def validate_document(document: ModelDocument) -> list[Diagnostic]:
    return validate_entity_model(document.model, file=document.path)


def _validate_duplicate_names(
    model: SourceModel | ModelSlice,
    file: Path | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    buckets = (
        ("entity", [item.name for item in model.entities]),
        ("enum", [item.name for item in model.enums]),
        ("type", [item.name for item in model.types]),
    )
    seen: dict[str, str] = {}
    for kind, names in buckets:
        local: set[str] = set()
        for index, name in enumerate(names):
            if name in local:
                diagnostics.append(
                    error(
                        "MG002",
                        f"дубликат имени {kind}: {name}",
                        file=file,
                        path=f"{kind}[{index}]",
                        entity=name,
                    )
                )
            local.add(name)
            previous = seen.get(name)
            if previous is not None and previous != kind:
                diagnostics.append(
                    error(
                        "MG002",
                        f"имя {name} используется и как {previous}, и как {kind}",
                        file=file,
                        path=f"{kind}[{index}]",
                        entity=name,
                    )
                )
            else:
                seen[name] = kind
    return diagnostics


def _validate_case_collisions(
    model: SourceModel | ModelSlice,
    file: Path | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    names = [item.name for item in (*model.entities, *model.enums, *model.types)]
    by_lower: dict[str, str] = {}
    for name in names:
        lower = name.lower()
        previous = by_lower.get(lower)
        if previous is not None and previous != name:
            diagnostics.append(
                warning(
                    "MG026",
                    f"case-insensitive коллизия имён: {previous} и {name}",
                    file=file,
                    entity=name,
                )
            )
        else:
            by_lower[lower] = name
    return diagnostics


def _resolve_type_bases(
    model: SourceModel | ModelSlice,
    primitives: set[str],
    file: Path | None,
    diagnostics: list[Diagnostic],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    type_map = {item.name: item for item in model.types}
    enum_names = {item.name for item in model.enums}

    def resolve(custom_type: CustomType, stack: tuple[str, ...]) -> str | None:
        if custom_type.name in stack:
            diagnostics.append(
                error(
                    "MG020",
                    f"цикл CustomType.base: {' -> '.join((*stack, custom_type.name))}",
                    file=file,
                    entity=custom_type.name,
                )
            )
            return None
        if len(stack) > MAX_TYPE_DEPTH:
            diagnostics.append(
                error(
                    "MG020",
                    f"глубина CustomType.base больше {MAX_TYPE_DEPTH}",
                    file=file,
                    entity=custom_type.name,
                )
            )
            return None
        base = custom_type.base
        if base in primitives:
            return base
        if base in enum_names:
            diagnostics.append(
                error(
                    "MG004",
                    f"CustomType.base не может ссылаться на enum: {base}",
                    file=file,
                    entity=custom_type.name,
                )
            )
            return None
        parent = type_map.get(base)
        if parent is None:
            diagnostics.append(
                error(
                    "MG004",
                    f"неизвестный базовый тип {base} у {custom_type.name}",
                    file=file,
                    entity=custom_type.name,
                )
            )
            return None
        return resolve(parent, (*stack, custom_type.name))

    for custom_type in model.types:
        base = resolve(custom_type, ())
        if base is not None:
            resolved[custom_type.name] = base
    return resolved


def _validate_enum(enum: EnumDef, file: Path | None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not enum.values:
        diagnostics.append(error("MG019", f"enum {enum.name} пуст", file=file, entity=enum.name))
    names: set[str] = set()
    values: set[tuple[str, Any]] = set()
    for index, item in enumerate(enum.values):
        if item.name in names:
            diagnostics.append(
                error(
                    "MG019",
                    f"дубликат имени значения enum {enum.name}: {item.name}",
                    file=file,
                    entity=enum.name,
                    field=item.name,
                    path=f"enums[{index}]",
                )
            )
        names.add(item.name)
        value = item.value if item.value is not None else item.name
        marker = (type(value).__name__, value)
        if marker in values:
            diagnostics.append(
                error(
                    "MG019",
                    f"дубликат значения enum {enum.name}: {value!r}",
                    file=file,
                    entity=enum.name,
                    field=item.name,
                    path=f"enums[{index}]",
                )
            )
        values.add(marker)
    return diagnostics


def _validate_entity(
    entity: Entity,
    model: SourceModel | ModelSlice,
    primitives: set[str],
    type_bases: dict[str, str],
    referenced: set[str],
    file: Path | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", entity.name):
        diagnostics.append(
            warning(
                "MG012",
                f"entity {entity.name} не в PascalCase",
                file=file,
                entity=entity.name,
            )
        )
    if len({field.name for field in entity.fields}) != len(entity.fields):
        seen: set[str] = set()
        for index, field in enumerate(entity.fields):
            if field.name in seen:
                diagnostics.append(
                    error(
                        "MG003",
                        f"дубликат поля {field.name} в {entity.name}",
                        file=file,
                        entity=entity.name,
                        field=field.name,
                        path=f"entities[{entity.name}].fields[{index}]",
                    )
                )
            seen.add(field.name)

    enum_map = {item.name: item for item in model.enums}
    type_map = {item.name: item for item in model.types}
    for index, field in enumerate(entity.fields):
        location = {
            "file": file,
            "entity": entity.name,
            "field": field.name,
            "path": f"entities[{entity.name}].fields[{index}]",
        }
        if field.type in enum_map or field.type in type_map:
            referenced.add(field.type)
        elif field.type in primitives:
            pass
        else:
            diagnostics.append(error("MG004", f"неизвестный тип {field.type}", **location))

        if field.default is None and not field.nullable:
            diagnostics.append(
                error(
                    "MG010",
                    "default: null недопустим при nullable: false",
                    **location,
                )
            )
        if field.required and field.nullable:
            diagnostics.append(
                warning(
                    "MG011",
                    "required: true и nullable: true — валидно только для PATCH",
                    **location,
                )
            )
        if field.required and not field.description:
            diagnostics.append(
                warning(
                    "MG015",
                    f"у обязательного поля {field.name} нет description",
                    **location,
                )
            )

        effective = type_bases.get(field.type, field.type)
        constraints = _merge_constraints(field, type_map.get(field.type))
        diagnostics.extend(_validate_constraints(constraints, effective, location))
        if field.default is not UNSET and field.default is not None:
            diagnostics.extend(
                _validate_default(
                    field.default,
                    effective,
                    enum_map.get(field.type),
                    constraints,
                    location,
                )
            )
    return diagnostics


def _merge_constraints(
    field: FieldDef,
    custom_type: CustomType | None,
) -> Constraints | None:
    if field.constraints is None:
        return custom_type.constraints if custom_type is not None else None
    if custom_type is None or custom_type.constraints is None:
        return field.constraints

    base = custom_type.constraints
    override = field.constraints
    values: dict[str, Any] = {}
    for name in ("min", "max", "min_length", "max_length", "pattern"):
        if name in override.model_fields_set:
            values[name] = getattr(override, name)
        else:
            values[name] = getattr(base, name)
    return Constraints(**values)


def _validate_constraints(
    constraints: Constraints | None,
    base_type: str,
    location: dict[str, Any],
) -> list[Diagnostic]:
    if constraints is None:
        return []
    diagnostics: list[Diagnostic] = []
    string_like = base_type in {"string", "text", "uuid"}
    numeric = base_type in {"integer", "bigint", "float"}
    temporal = base_type in {"date", "datetime"}

    if constraints.pattern is not None and not string_like:
        diagnostics.append(error("MG021", "pattern применим только к строковым типам", **location))
    if (constraints.min_length is not None or constraints.max_length is not None) and not (
        string_like
    ):
        diagnostics.append(
            error(
                "MG021",
                "min_length/max_length применимы только к строковым типам",
                **location,
            )
        )
    if (constraints.min is not None or constraints.max is not None) and not (numeric or temporal):
        diagnostics.append(error("MG021", "min/max применимы только к числам и датам", **location))
    if (
        constraints.min is not None
        and constraints.max is not None
        and _safe_compare(constraints.min, constraints.max) > 0
    ):
        diagnostics.append(error("MG021", "min больше max", **location))
    if (
        constraints.min_length is not None
        and constraints.max_length is not None
        and constraints.min_length > constraints.max_length
    ):
        diagnostics.append(error("MG021", "min_length больше max_length", **location))
    if constraints.pattern is not None:
        try:
            re.compile(constraints.pattern)
        except re.error as exc:
            diagnostics.append(error("MG005", f"некорректный regex: {exc}", **location))
    return diagnostics


def _validate_default(
    default: object,
    base_type: str,
    enum: EnumDef | None,
    constraints: Constraints | None,
    location: dict[str, Any],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if enum is not None:
        values = {item.value if item.value is not None else item.name for item in enum.values}
        names = {item.name for item in enum.values}
        if default not in values and default not in names:
            diagnostics.append(
                error(
                    "MG017",
                    f"default {default!r} отсутствует в enum {enum.name}",
                    **location,
                )
            )
        return diagnostics

    valid = _default_matches_type(default, base_type)
    if not valid:
        diagnostics.append(
            error(
                "MG016",
                f"default {default!r} не соответствует типу {base_type}",
                **location,
            )
        )
        return diagnostics
    if constraints is not None:
        diagnostics.extend(_validate_default_constraints(default, constraints, location))
    return diagnostics


def _default_matches_type(value: object, base_type: str) -> bool:
    if base_type in {"string", "text"}:
        return isinstance(value, str)
    if base_type == "uuid":
        return isinstance(value, str)
    if base_type in {"integer", "bigint"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if base_type == "boolean":
        return isinstance(value, bool)
    if base_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base_type == "date":
        return isinstance(value, date) and not isinstance(value, datetime)
    if base_type == "datetime":
        return isinstance(value, datetime)
    return True


def _validate_default_constraints(
    value: object,
    constraints: Constraints,
    location: dict[str, Any],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        if constraints.min is not None and _safe_compare(value, constraints.min) < 0:
            diagnostics.append(
                error("MG017", f"default {value!r} меньше min {constraints.min!r}", **location)
            )
        if constraints.max is not None and _safe_compare(value, constraints.max) > 0:
            diagnostics.append(
                error("MG017", f"default {value!r} больше max {constraints.max!r}", **location)
            )
    except TypeError:
        diagnostics.append(error("MG017", f"default {value!r} не сравним с min/max", **location))
    if isinstance(value, str):
        if constraints.min_length is not None and len(value) < constraints.min_length:
            diagnostics.append(
                error("MG017", f"default короче min_length {constraints.min_length}", **location)
            )
        if constraints.max_length is not None and len(value) > constraints.max_length:
            diagnostics.append(
                error("MG017", f"default длиннее max_length {constraints.max_length}", **location)
            )
        if constraints.pattern is not None and not re.fullmatch(constraints.pattern, value):
            diagnostics.append(
                error(
                    "MG017",
                    f"default не соответствует pattern {constraints.pattern!r}",
                    **location,
                )
            )
    return diagnostics


def _safe_compare(left: object, right: object) -> int:
    if left < right:  # type: ignore[operator]
        return -1
    if left > right:  # type: ignore[operator]
        return 1
    return 0


__all__ = ["validate_document", "validate_entity_model"]
