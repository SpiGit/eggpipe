"""Тесты Engine: build/generate/check."""

from __future__ import annotations

from pathlib import Path

import pytest

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    GeneratorRules,
    SourceConfig,
)
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
    name = "Demo"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(artifacts=[Artifact(path="user.txt", content="ok\n")])


class FailingGenerator(GeneratorPlugin):
    id = "fail"
    name = "Fail"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        raise RuntimeError("boom")


def make_rules(generator_id: str = "demo") -> GeneratorRules:
    return GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml")),),
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
    assert (tmp_path / "out" / ".eggpipe" / "manifests" / "demo.json").is_file()
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
