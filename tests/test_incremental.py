"""Tests for opt-in incremental generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    ProjectConfig,
    SourceConfig,
)

MODEL = """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
"""


class CountingGenerator(GeneratorPlugin):
    id = "counting"
    name = "Counting"
    input_formats: ClassVar[set[str] | None] = None
    __version__ = "1"
    calls = 0

    def generate(self, input: GeneratorInput) -> GenerationResult:
        type(self).calls += 1
        names = ",".join(entity.name for entity in input.model.entities)
        return GenerationResult(artifacts=[Artifact(path="out.txt", content=names + "\n")])


def make_engine(
    tmp_path: Path,
    *,
    incremental: bool = True,
    force: bool = False,
    allow_outside_imports: bool = False,
) -> Engine:
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id="counting", output_dir=Path("out")),),
    )
    return Engine(
        AppConfig(
            incremental=incremental,
            force=force,
            allow_outside_imports=allow_outside_imports,
        ),
        rules,
        config_dir=tmp_path,
        generators={"counting": CountingGenerator()},
    )


def test_incremental_skips_unchanged_generation(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")

    first = make_engine(tmp_path).generate()
    assert first.success is True
    assert CountingGenerator.calls == 1

    second = make_engine(tmp_path).generate()
    assert second.success is True
    assert CountingGenerator.calls == 1
    assert second.generators[0].status == "skipped"
    assert second.artifacts[0].action == "skip"
    manifest = json.loads((tmp_path / ".eggpipe" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["locations"][0]["input_fingerprint"]


MODEL_V2 = """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
        - name: name
          type: string
"""


def test_incremental_invalidates_on_model_change(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    model = tmp_path / "model.yaml"
    model.write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    model.write_text(MODEL_V2, encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_invalidates_on_variables(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id="counting", output_dir=Path("out")),),
    )
    Engine(
        AppConfig(incremental=True),
        rules,
        config_dir=tmp_path,
        generators={"counting": CountingGenerator()},
        variables={"env": "prod"},
    ).generate()
    assert CountingGenerator.calls == 2


def test_incremental_can_be_disabled(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    make_engine(tmp_path, incremental=False).generate()
    assert CountingGenerator.calls == 2


def test_check_bypasses_incremental_cache(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    make_engine(tmp_path).check()
    assert CountingGenerator.calls == 2


def test_incremental_invalidates_on_artifact_change(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    (tmp_path / "out" / "out.txt").write_text("tampered\n", encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_invalidates_when_manifest_is_missing(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    (tmp_path / ".eggpipe" / "manifest.json").unlink()
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_is_disabled_with_force(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    make_engine(tmp_path, force=True).generate()
    assert CountingGenerator.calls == 2


def test_incremental_is_disabled_with_outside_imports(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    make_engine(tmp_path, allow_outside_imports=True).generate()
    assert CountingGenerator.calls == 2
