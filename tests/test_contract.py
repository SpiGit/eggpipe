"""Contract-тесты публичных интерфейсов плагинов."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from eggpipe import (
    Artifact,
    Diagnostic,
    EntityIdentity,
    FieldIdentity,
    FormatInfo,
    GenerationContext,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    MergePolicy,
    ModelSlice,
)


class Demo(GeneratorPlugin):
    id = "demo"
    input_formats: ClassVar[set[str] | None] = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


def test_generator_input_is_frozen_and_validated() -> None:
    input = GeneratorInput(
        model=ModelSlice(),
        config=GeneratorConfig(id="demo", output_dir=Path("out")),
        context=GenerationContext(
            formats=frozenset({FormatInfo(name="entity-model", version="1.0")}),
            run_id="run",
            config_dir=Path("."),
        ),
    )
    with pytest.raises(ValidationError):
        input.model = ModelSlice()  # type: ignore[misc]


def test_format_public_models() -> None:
    assert MergePolicy.KEYED == "keyed"
    assert MergePolicy.APPEND == "append"
    assert MergePolicy.UNION == "union"
    assert MergePolicy.ERROR == "error"
    left = FormatInfo(name="entity-model", version="1.0")
    right = FormatInfo(name="entity-model", version="1.0")
    assert left == right
    assert hash(left) == hash(right)
    assert EntityIdentity(name="User").name == "User"
    assert FieldIdentity(name="id").name == "id"


def test_generation_result_success() -> None:
    assert GenerationResult().success is True
    failed = GenerationResult(
        artifacts=[Artifact(path="a.txt", content="a")],
        errors=[Diagnostic(level="error", code="MG300", message="failed")],
    )
    assert failed.success is False


def test_generator_contract_defaults() -> None:
    generator = Demo()
    assert generator.api_version == "1"
    assert generator.name == ""
    assert generator.validate_config(GeneratorConfig(id="demo", output_dir=Path("out"))) == []
