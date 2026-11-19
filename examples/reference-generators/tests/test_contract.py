"""Contract tests for the reference generators."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from eggpipe_reference_generators import (
    openapi_generator,
    pydantic_generator,
    sql_generator,
    typescript_generator,
)

from eggpipe import (
    CustomType,
    Entity,
    FieldDef,
    GenerationContext,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    ModelSlice,
)
from eggpipe.interfaces.generator import validate_generator_contract

GeneratorFactory = Callable[[], GeneratorPlugin]

CASES = [
    (sql_generator, "sql", "schema.sql"),
    (pydantic_generator, "pydantic", "models.py"),
    (typescript_generator, "typescript", "models.ts"),
    (openapi_generator, "openapi", "openapi.json"),
]

CONTENT = [
    (sql_generator, ["CREATE TABLE user (", "id INTEGER NOT NULL", "created_at TIMESTAMP"]),
    (pydantic_generator, ["class User(BaseModel):", "id: int", "email: str | None = None"]),
    (typescript_generator, ["export interface User {", "id: number;", "email?: string;"]),
    (openapi_generator, ['"openapi": "3.1.0"', '"User"', '"required"']),
]


def sample_input(generator_id: str) -> GeneratorInput:
    model = ModelSlice(
        entities=(
            Entity(
                name="User",
                fields=(
                    FieldDef(name="id", type="integer", required=True),
                    FieldDef(name="email", type="Email"),
                    FieldDef(name="createdAt", type="datetime", nullable=True),
                ),
            ),
            Entity(
                name="Account",
                fields=(FieldDef(name="id", type="uuid", required=True),),
            ),
        ),
        types=(CustomType(name="Email", base="string"),),
    )
    return GeneratorInput(
        model=model,
        config=GeneratorConfig(id=generator_id, output_dir=Path("out")),
        context=GenerationContext(run_id="test-run", config_dir=Path(".")),
    )


@pytest.mark.parametrize(("factory", "generator_id", "artifact_path"), CASES)
def test_contract(factory: GeneratorFactory, generator_id: str, artifact_path: str) -> None:
    plugin = factory()
    validate_generator_contract(plugin)
    assert plugin.id == generator_id
    assert plugin.output_scope == "model"
    assert plugin.input_formats == {"entity-model"}

    result = plugin.generate(sample_input(generator_id))
    assert result.success is True
    assert [artifact.path for artifact in result.artifacts] == [artifact_path]


@pytest.mark.parametrize(("factory", "fragments"), CONTENT)
def test_content(factory: GeneratorFactory, fragments: list[str]) -> None:
    plugin = factory()
    content = plugin.generate(sample_input(plugin.id)).artifacts[0].content
    for fragment in fragments:
        assert fragment in content
    # The custom type `Email` resolves to a string; every artifact ends with LF.
    assert content.endswith("\n")


@pytest.mark.parametrize(("factory", "generator_id", "_artifact_path"), CASES)
def test_determinism(factory: GeneratorFactory, generator_id: str, _artifact_path: str) -> None:
    plugin = factory()
    first = plugin.generate(sample_input(generator_id)).artifacts[0].content
    second = plugin.generate(sample_input(generator_id)).artifacts[0].content
    assert first == second


@pytest.mark.parametrize(("factory", "generator_id", "_artifact_path"), CASES)
def test_generators_ignore_options(
    factory: GeneratorFactory, generator_id: str, _artifact_path: str
) -> None:
    plugin = factory()
    baseline = plugin.generate(sample_input(generator_id)).artifacts[0].content
    configured = GeneratorInput(
        model=sample_input(generator_id).model,
        config=GeneratorConfig(id=generator_id, output_dir=Path("out"), options={"x": 1}),
        context=GenerationContext(run_id="test-run", config_dir=Path(".")),
    )
    assert plugin.generate(configured).artifacts[0].content == baseline


def test_entry_points_are_registered() -> None:
    from eggpipe.engine.plugin_loader import load_generators_with_issues

    plugins, _issues = load_generators_with_issues()
    assert {"sql", "pydantic", "typescript", "openapi"} <= set(plugins)
    assert len({plugin.id for plugin in plugins.values()}) == len(plugins)


def test_entity_order_is_stable() -> None:
    content = sql_generator().generate(sample_input("sql")).artifacts[0].content
    assert content.index("CREATE TABLE account") < content.index("CREATE TABLE user")
