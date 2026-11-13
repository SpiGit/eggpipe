"""Reference-генератор для examples и golden-тестов."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from eggpipe import (
    UNSET,
    Artifact,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
)


class ReferenceGenerator(GeneratorPlugin):
    """Детерминированный вывод модели в JSON — эталон для golden-тестов."""

    id = "reference"
    name = "Reference Generator"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        payload = {
            "format": input.context.format,
            "version": input.context.format_version,
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
