"""Contract tests for the template plugin."""

from __future__ import annotations

from pathlib import Path

from eggpipe_plugin_template import TemplateFormat, template_generator

from eggpipe import (
    Entity,
    FieldDef,
    GenerationContext,
    GeneratorConfig,
    GeneratorInput,
    ModelSlice,
)
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.interfaces.generator import validate_generator_contract


def sample_input() -> GeneratorInput:
    entity = Entity(
        name="User",
        fields=(
            FieldDef(name="id", type="integer", required=True),
            FieldDef(name="email", type="string"),
        ),
    )
    return GeneratorInput(
        model=ModelSlice(entities=(entity,)),
        config=GeneratorConfig(id="template-json", output_dir=Path("out")),
        context=GenerationContext(run_id="test-run", config_dir=Path(".")),
    )


def test_generator_contract() -> None:
    plugin = template_generator()
    validate_generator_contract(plugin)
    assert plugin.id == "template-json"
    assert plugin.name == "Template JSON"
    assert plugin.input_formats == {"entity-model", "template-model"}


def test_generator_output() -> None:
    result = template_generator().generate(sample_input())
    assert result.success is True
    assert len(result.artifacts) == 1
    assert result.artifacts[0].path == "template.json"
    assert '"name": "User"' in result.artifacts[0].content
    assert '"name": "email"' in result.artifacts[0].content


def test_format_contract() -> None:
    registry = FormatRegistry()
    registry.register(TemplateFormat())
    plugin = registry.get("template-model")
    assert plugin.format_names == ["template-model"]
    assert plugin.supported_versions == ["1.0"]
    assert registry.accepts("template-model", {"entity-model"}) is True
