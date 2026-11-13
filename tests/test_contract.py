"""Contract-тесты публичных интерфейсов плагинов."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from eggpipe import (
    Artifact,
    Diagnostic,
    GenerationContext,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    ModelSlice,
)


class Demo(GeneratorPlugin):
    id = "demo"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


def test_generator_input_is_frozen_and_validated() -> None:
    input = GeneratorInput(
        model=ModelSlice(),
        config=GeneratorConfig(id="demo", output_dir=Path("out")),
        context=GenerationContext(
            format="entity-model",
            format_version="1.0",
            run_id="run",
            config_dir=Path("."),
        ),
    )
    with pytest.raises(ValidationError):
        input.model = ModelSlice()  # type: ignore[misc]


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
