"""Reference generator for examples and golden tests."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, ClassVar

from eggpipe import (
    UNSET,
    Artifact,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
)


class ReferenceGenerator(GeneratorPlugin):
    """Deterministic JSON dump of the model — the baseline for golden tests."""

    id = "reference"
    name = "Reference Generator"
    input_formats: ClassVar[set[str] | None] = {"entity-model"}

    def generate(self, input: GeneratorInput) -> GenerationResult:
        payload = {
            "formats": [
                {"name": item.name, "version": item.version}
                for item in sorted(
                    input.context.formats, key=lambda item: (item.name, item.version)
                )
            ],
            "entities": [
                {
                    "name": entity.name,
                    "fields": [
                        {
                            "name": field.name,
                            "type": field.type,
                            "required": field.required,
                            "nullable": field.nullable,
                            "default": _default_value(field.default),
                        }
                        for field in entity.fields
                    ],
                }
                for entity in input.model.entities
            ],
            "enums": [
                {
                    "name": enum.name,
                    "values": [
                        {
                            "name": value.name,
                            "value": value.value if value.value is not None else value.name,
                        }
                        for value in enum.values
                    ],
                }
                for enum in input.model.enums
            ],
            "types": [{"name": custom.name, "base": custom.base} for custom in input.model.types],
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        return GenerationResult(artifacts=[Artifact(path="model.json", content=content)])


def _default_value(value: Any) -> Any:
    if value is UNSET:
        return "UNSET"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


__all__ = ["ReferenceGenerator"]
