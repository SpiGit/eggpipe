"""Template generator and format plugin for eggpipe."""

from __future__ import annotations

import json
from typing import ClassVar

from eggpipe import (
    Artifact,
    EntityModelFormat,
    GenerationContext,
    GeneratorConfig,
    ModelSlice,
    generator,
)


class TemplateFormat(EntityModelFormat):
    """Example format that extends the built-in entity-model format."""

    format_names: ClassVar[list[str]] = ["template-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}


@generator(
    id="template-json",
    name="Template JSON",
    input_formats={"entity-model", "template-model"},
)
def template_generator(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    """Write a deterministic JSON snapshot of the input model."""
    payload = {
        "generator": config.id,
        "run_id": context.run_id,
        "variables": dict(sorted(context.variables.items())),
        "formats": [
            {"name": item.name, "version": item.version}
            for item in sorted(context.formats, key=lambda item: (item.name, item.version))
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
                    }
                    for field in entity.fields
                ],
            }
            for entity in model.entities
        ],
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return [Artifact(path="template.json", content=content)]


__all__ = ["TemplateFormat", "template_generator"]
