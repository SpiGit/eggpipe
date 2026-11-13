"""Determinism tests for repeated generation."""

from __future__ import annotations

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


class StableGenerator(GeneratorPlugin):
    id = "stable"
    input_formats: ClassVar[set[str] | None] = None
    name = "Stable"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        lines = [entity.name for entity in input.model.entities]
        return GenerationResult(
            artifacts=[Artifact(path="stable.txt", content="\n".join(lines) + "\n")]
        )


def test_repeated_generation_is_byte_identical(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(
        """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
""",
        encoding="utf-8",
    )
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(GeneratorConfig(id="stable", output_dir=Path("out")),),
    )

    def run() -> bytes:
        engine = Engine(
            AppConfig(),
            rules,
            config_dir=tmp_path,
            generators={"stable": StableGenerator()},
        )
        assert engine.generate().success is True
        return (tmp_path / "out" / "stable.txt").read_bytes()

    first = run()
    second = run()
    assert first == second
