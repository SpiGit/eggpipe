"""Тесты decorator API и проверки input_formats."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    GenerationContext,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    GeneratorRules,
    ModelSlice,
    SourceConfig,
    generator,
)
from eggpipe.engine.plugin_loader import PluginIssue
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
          description: Identifier
"""


def context() -> GenerationContext:
    return GenerationContext(run_id="run", config_dir=Path("."))


def config(generator_id: str = "demo") -> GeneratorConfig:
    return GeneratorConfig(id=generator_id, output_dir=Path("out"))


def input_for(model: ModelSlice, generator_id: str = "demo") -> GeneratorInput:
    return GeneratorInput(model=model, config=config(generator_id), context=context())


@generator(input_formats={"entity-model"})
def list_artifacts(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [Artifact(path="a.txt", content=f"{len(model.entities)}:{config.id}\n")]


@generator(id="single", name="Single", input_formats=None)
def single(model: ModelSlice) -> Artifact:
    return Artifact(path="single.txt", content=str(len(model.entities)))


@generator(input_formats=set())
def as_tuple(model: ModelSlice) -> tuple[Artifact, ...]:
    return (Artifact(path="tuple.txt", content=str(len(model.enums))),)


@generator(input_formats=None)
def as_result(model: ModelSlice) -> GenerationResult:
    return GenerationResult(
        artifacts=[Artifact(path="result.txt", content=str(len(model.entities)))]
    )


def test_decorator_metadata_and_injection() -> None:
    plugin = list_artifacts()
    assert isinstance(plugin, GeneratorPlugin)
    assert plugin.id == "list-artifacts"
    assert plugin.name == "List Artifacts"
    assert plugin.input_formats == {"entity-model"}

    result = plugin.generate(input_for(ModelSlice()))
    assert result.success is True
    assert result.artifacts[0].path == "a.txt"
    assert result.artifacts[0].content == "0:demo\n"


def test_decorator_normalizes_return_types() -> None:
    model = ModelSlice()
    assert single().generate(input_for(model, "single")).artifacts[0].path == "single.txt"
    assert as_tuple().generate(input_for(model)).artifacts[0].path == "tuple.txt"
    assert as_result().generate(input_for(model)).artifacts[0].path == "result.txt"


def test_decorator_requires_input_formats() -> None:
    def plain(model: ModelSlice) -> Artifact:
        return Artifact(path="a.txt", content="a")

    with pytest.raises(PluginContractError) as caught:
        generator()(plain)
    assert caught.value.code == "MG301"


def test_unknown_injection_parameter() -> None:
    def bad(value: str) -> Artifact:
        return Artifact(path="a.txt", content=value)

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(bad)
    assert caught.value.code == "MG302"


def test_missing_annotation_and_return_type() -> None:
    def missing(model) -> Artifact:  # type: ignore[implicit-any-parameter]
        return Artifact(path="a.txt", content="a")

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(missing)
    assert caught.value.code == "MG301"

    def bad_return(model: ModelSlice) -> str:
        return "a"

    with pytest.raises(PluginContractError) as caught:
        validate_generator_function(bad_return)
    assert caught.value.code == "MG301"


def test_class_contract_requires_input_formats() -> None:
    class Missing(GeneratorPlugin):
        id = "missing"

        def generate(self, input: GeneratorInput) -> GenerationResult:
            return GenerationResult()

    with pytest.raises(PluginContractError) as caught:
        validate_generator_contract(Missing())
    assert caught.value.code == "MG301"


class NoFormats(GeneratorPlugin):
    id = "no-formats"
    input_formats: ClassVar[set[str] | None] = set()

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class InheritsBase(GeneratorPlugin):
    id = "inherits-base"
    input_formats: ClassVar[set[str] | None] = {"entity-model"}

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


def engine_with(tmp_path: Path, plugin: GeneratorPlugin) -> Engine:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    rules = GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id=plugin.id, output_dir=Path("out")),),
    )
    return Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={plugin.id: plugin},
    )


def test_incompatible_input_formats_is_preflight_mg033(tmp_path: Path) -> None:
    report = engine_with(tmp_path, NoFormats()).generate()
    assert report.success is False
    assert report.exit_code == 2
    assert [item.code for item in report.diagnostics] == ["MG033"]
    assert not (tmp_path / "out").exists()


def test_base_format_accepts_descendant(tmp_path: Path) -> None:
    report = engine_with(tmp_path, InheritsBase()).build()
    assert report.success is True
    assert report.exit_code == 0


def test_plugin_issue_has_code() -> None:
    issue = PluginIssue("entry", "message", "MG301")
    assert issue.code == "MG301"
