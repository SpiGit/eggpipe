"""Contract tests for public plugin interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from eggpipe import (
    AppConfig,
    Artifact,
    Diagnostic,
    Engine,
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
    ProjectConfig,
    SourceConfig,
)
from eggpipe.interfaces.generator import (
    validate_generator_contract,
    validate_generator_function,
)
from eggpipe.utils.exceptions import PluginContractError

MODEL = """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
"""


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
        errors=[Diagnostic(level="error", code="EG300", message="failed")],
    )
    assert failed.success is False


def test_generator_contract_defaults() -> None:
    generator = Demo()
    assert generator.api_version == "1"
    assert generator.name == ""
    assert generator.validate_config(GeneratorConfig(id="demo", output_dir=Path("out"))) == []


def test_eg301_missing_annotation_names_parameter_and_hint() -> None:
    def missing(model) -> Artifact:  # type: ignore[implicit-any-parameter,missing-return-type]
        return Artifact(path="a.txt", content="a")

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(missing)

    message = str(caught.value)
    assert caught.value.code == "EG301"
    assert "'model'" in message
    assert "no annotation" in message
    assert "ModelSlice, GenerationContext or GeneratorConfig" in message
    assert "test_contract" in message


def test_eg302_unknown_annotation_names_parameter_and_hint() -> None:
    def unsupported(model: ModelSlice, options: dict[str, str]) -> Artifact:
        return Artifact(path="a.txt", content=str(options))

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(unsupported)

    message = str(caught.value)
    assert caught.value.code == "EG302"
    assert "'options'" in message
    assert "unsupported annotation" in message
    assert "ModelSlice, GenerationContext or GeneratorConfig" in message


def test_eg301_class_contract_names_plugin_and_hint() -> None:
    class MissingFormats(GeneratorPlugin):
        id = "missing-formats"

        def generate(self, input: GeneratorInput) -> GenerationResult:
            return GenerationResult()

    with pytest.raises(PluginContractError) as caught:
        validate_generator_contract(MissingFormats())

    message = str(caught.value)
    assert caught.value.code == "EG301"
    assert "MissingFormats" in message
    assert "test_contract" in message
    assert "input_formats is not declared" in message
    assert "declare input_formats = {'entity-model'} or None" in message


def test_eg301_invalid_return_names_function_and_hint() -> None:
    def bad_return(model: ModelSlice) -> str:
        return model.model_dump_json()

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(bad_return)

    message = str(caught.value)
    assert caught.value.code == "EG301"
    assert "bad_return" in message
    assert "unsupported return annotation" in message
    assert "GenerationResult" in message


def test_engine_eg301_input_formats_includes_hint(tmp_path: Path) -> None:
    class MissingFormats(GeneratorPlugin):
        id = "missing-formats"

        def generate(self, input: GeneratorInput) -> GenerationResult:
            return GenerationResult()

    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id="missing-formats", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"missing-formats": MissingFormats()},
    )
    report = engine.generate()

    messages = [item.message for item in report.diagnostics if item.code == "EG301"]
    assert len(messages) == 1
    assert "missing-formats" in messages[0]
    assert "MissingFormats" in messages[0]
    assert "input_formats is not declared" in messages[0]
    assert "declare input_formats" in messages[0]
    assert "@generator" in messages[0]
