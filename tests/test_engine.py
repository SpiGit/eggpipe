"""Тесты Engine: build/generate/check."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    FormatInfo,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    GeneratorRules,
    SourceConfig,
)
from eggpipe.config.generator_rules import DiagnosticsConfig
from eggpipe.utils.exceptions import ConfigValidationError

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


class DemoGenerator(GeneratorPlugin):
    id = "demo"
    input_formats: ClassVar[set[str] | None] = None
    name = "Demo"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(artifacts=[Artifact(path="user.txt", content="ok\n")])


class FailingGenerator(GeneratorPlugin):
    id = "fail"
    input_formats: ClassVar[set[str] | None] = None
    name = "Fail"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        raise RuntimeError("boom")


class ContextGenerator(GeneratorPlugin):
    id = "context"
    input_formats: ClassVar[set[str] | None] = None
    name = "Context"

    def __init__(self) -> None:
        self.formats: frozenset[FormatInfo] = frozenset()

    def generate(self, input: GeneratorInput) -> GenerationResult:
        self.formats = input.context.formats
        return GenerationResult()


def make_rules(generator_id: str = "demo") -> GeneratorRules:
    return GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id=generator_id, output_dir=Path("out")),),
    )


def make_engine(tmp_path: Path, generator_id: str = "demo") -> Engine:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    generators: dict[str, GeneratorPlugin] = {
        "demo": DemoGenerator(),
        "fail": FailingGenerator(),
    }
    return Engine(
        AppConfig(),
        make_rules(generator_id),
        config_dir=tmp_path,
        generators=generators,
    )


def test_build_does_not_write(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    report = engine.build()
    assert report.success is True
    assert report.artifacts[0].status == "create"
    assert not (tmp_path / "out" / "user.txt").exists()


def test_generate_writes_and_check(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    report = engine.generate()
    assert report.success is True
    assert (tmp_path / "out" / "user.txt").read_text(encoding="utf-8") == "ok\n"
    assert (tmp_path / ".eggpipe" / "manifest.json").is_file()
    assert engine.check().success is True
    (tmp_path / "out" / "user.txt").write_text("drift", encoding="utf-8")
    assert engine.check().success is False


def test_generator_error_is_reported(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, "fail")
    report = engine.generate()
    assert report.success is False
    assert report.generators[0].status == "error"
    assert not (tmp_path / "out").exists()


def test_unknown_generator_is_config_error(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, "missing")
    with pytest.raises(ConfigValidationError):
        engine.build()


def test_generation_context_formats(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    generator = ContextGenerator()
    engine = Engine(
        AppConfig(),
        make_rules("context"),
        config_dir=tmp_path,
        generators={"context": generator},
    )
    assert engine.generate().success is True
    assert generator.formats == frozenset({FormatInfo(name="entity-model", version="1.0")})


def test_output_root(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    output_root = tmp_path / "build"
    engine = Engine(
        AppConfig(output_root=output_root),
        make_rules(),
        config_dir=tmp_path,
        generators={"demo": DemoGenerator()},
    )
    assert engine.generate().success is True
    assert (output_root / "out" / "user.txt").is_file()


def test_ignored_error_is_not_hidden(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(
        MODEL.replace("type: integer", "type: Missing"),
        encoding="utf-8",
    )
    rules = GeneratorRules(
        version="1.0",
        diagnostics=DiagnosticsConfig(ignore=frozenset({"MG004"})),
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id="demo", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"demo": DemoGenerator()},
    )
    report = engine.build()
    assert report.success is False
    assert "MG004" in {item.code for item in report.diagnostics}
