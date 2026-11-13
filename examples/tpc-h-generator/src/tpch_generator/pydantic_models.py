"""Prepare TPC-H data for the Pydantic v2 model Jinja2 template."""

from __future__ import annotations

import re
from pathlib import Path

from eggpipe import ModelSlice
from eggpipe.templating import jinja_environment, render_template
from tpch_generator.metadata import field_sql_type

_PARAMETERIZED = re.compile(
    r"^(?P<base>decimal|numeric|char|varchar)\((?P<args>\d+(?:\s*,\s*\d+)?)\)$"
)
_SIMPLE_TYPES = {
    "decimal": "Decimal",
    "numeric": "Decimal",
    "integer": "int",
    "int": "int",
    "bigint": "int",
    "smallint": "int",
    "boolean": "bool",
    "bool": "bool",
    "date": "date",
}


def render_pydantic(model: ModelSlice, templates_dir: Path | None = None) -> str:
    entities = []
    annotations: set[str] = set()
    for entity in model.entities:
        fields = []
        for field in entity.fields:
            annotation, constraints = _python_type(field_sql_type(field))
            annotations.add(annotation)
            fields.append(
                {
                    "name": field.name,
                    "annotation": annotation,
                    "constraints": constraints,
                    "optional": field.nullable or not field.required,
                }
            )
        entities.append({"name": entity.name, "fields": fields})

    environment = jinja_environment(package="tpch_generator", templates_dir=templates_dir)
    return render_template(
        environment,
        "pydantic.py.j2",
        entities=entities,
        annotations=annotations,
    )


def _python_type(sql_type: str) -> tuple[str, dict[str, int]]:
    """Map a SQL type to a Python annotation and Pydantic constraints."""
    normalized = sql_type.strip().lower()
    match = _PARAMETERIZED.match(normalized)
    if match:
        base = match.group("base")
        args = [int(arg) for arg in match.group("args").replace(" ", "").split(",")]
        if base in {"decimal", "numeric"}:
            if len(args) == 2:
                return "Decimal", {"max_digits": args[0], "decimal_places": args[1]}
            return "Decimal", {}
        return "str", {"max_length": args[0]}
    if normalized.startswith("timestamp"):
        return "datetime", {}
    return _SIMPLE_TYPES.get(normalized, "str"), {}
