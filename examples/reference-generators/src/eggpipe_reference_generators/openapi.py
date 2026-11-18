"""OpenAPI 3.1 schemas generator (`openapi.json`)."""

from __future__ import annotations

import json
from typing import Any

from eggpipe import Artifact, FieldDef, ModelSlice, generator
from eggpipe_reference_generators._common import (
    camel_case,
    pascal_case,
    primitive_type,
    sorted_entities,
)

_OPENAPI_TYPES: dict[str, dict[str, str]] = {
    "string": {"type": "string"},
    "text": {"type": "string"},
    "integer": {"type": "integer"},
    "bigint": {"type": "integer", "format": "int64"},
    "boolean": {"type": "boolean"},
    "float": {"type": "number", "format": "double"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "uuid": {"type": "string", "format": "uuid"},
    "json": {"type": "object"},
}


@generator(
    id="openapi",
    name="OpenAPI Schemas",
    input_formats={"entity-model"},
)
def openapi_generator(model: ModelSlice) -> list[Artifact]:
    """Generate `openapi.json` with components.schemas per entity."""
    schemas = {
        pascal_case(entity.name): _entity_schema(entity.fields, model)
        for entity in sorted_entities(model)
    }
    document: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": "Eggpipe model", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": schemas},
    }
    content = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return [Artifact(path="openapi.json", content=content)]


def _entity_schema(fields: tuple[FieldDef, ...], model: ModelSlice) -> dict[str, Any]:
    properties = {camel_case(field.name): _property(field, model) for field in fields}
    required = [camel_case(field.name) for field in fields if field.required]
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _property(field: FieldDef, model: ModelSlice) -> dict[str, Any]:
    base: dict[str, Any] = dict(_OPENAPI_TYPES[primitive_type(field.type, model)])
    if field.nullable:
        base["type"] = [base["type"], "null"]
    return base


__all__ = ["openapi_generator"]
