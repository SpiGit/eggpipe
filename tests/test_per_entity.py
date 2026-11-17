"""Tests for per-entity generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Literal

import pytest

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    InputSelection,
    ProjectConfig,
    SourceConfig,
    generator,
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
    - name: Post
      fields:
        - name: id
          type: integer
"""


class PerEntityGenerator(GeneratorPlugin):
    id = "per-entity"
    name = "Per entity"
    input_formats: ClassVar[set[str] | None] = None
    output_scope: ClassVar[Literal["entity"]] = "entity"
    __version__ = "1"
    calls = 0
    last_entities: ClassVar[tuple[str, ...]] = ()

    def generate(self, input: GeneratorInput) -> GenerationResult:
        type(self).calls += 1
        type(self).last_entities = tuple(entity.name for entity in input.model.entities)
        return GenerationResult(
            artifacts=[
                Artifact(path=f"{entity.name.lower()}.txt", content=f"{entity.name}\n")
                for entity in input.model.entities
            ]
        )


class ModelGenerator(GeneratorPlugin):
    id = "model"
    name = "Model"
    input_formats: ClassVar[set[str] | None] = None
    __version__ = "1"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(artifacts=[Artifact(path="all.txt", content="all\n")])


def make_engine(
    tmp_path: Path,
    *,
    generator_id: str = "per-entity",
    plugin: GeneratorPlugin | None = None,
    cleanup: Literal["off", "prompt", "enabled"] = "off",
    incremental: bool = False,
    clean: bool = False,
    input_entities: tuple[str, ...] | None = None,
) -> Engine:
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(
            GeneratorConfig(
                id=generator_id,
                output_dir=Path("out"),
                cleanup=cleanup,
                input=InputSelection(entities=input_entities),
            ),
        ),
    )
    selected = plugin or PerEntityGenerator()
    return Engine(
        AppConfig(incremental=incremental, clean=clean),
        rules,
        config_dir=tmp_path,
        generators={generator_id: selected},
    )


def test_per_entity_generates_only_selected_entity(tmp_path: Path) -> None:
    PerEntityGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")

    report = make_engine(tmp_path).generate(entities=["User"])

    assert report.success is True
    assert (tmp_path / "out" / "user.txt").is_file()
    assert not (tmp_path / "out" / "post.txt").exists()
    manifest = json.loads((tmp_path / ".eggpipe" / "manifest.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["locations"][0]["artifacts"]] == ["user.txt"]


def test_per_entity_merges_manifest_and_keeps_other_artifacts(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path)
    assert engine.generate().success is True

    report = engine.generate(entities=["User"])

    assert report.success is True
    assert (tmp_path / "out" / "user.txt").is_file()
    assert (tmp_path / "out" / "post.txt").is_file()
    manifest = json.loads((tmp_path / ".eggpipe" / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["locations"][0]["artifacts"]}
    assert paths == {"user.txt", "post.txt"}


def test_per_entity_requires_entity_scope(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="model", plugin=ModelGenerator()).generate(
        entities=["User"]
    )

    assert report.success is False
    assert report.exit_code == 2
    assert any(item.code == "EG303" for item in report.diagnostics)
    assert not (tmp_path / "out" / "all.txt").exists()


def test_per_entity_rejects_unknown_entity(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path).generate(entities=["Missing"])

    assert report.success is False
    assert any(item.code == "EG018" for item in report.diagnostics)
    assert not (tmp_path / "out").exists()


def test_per_entity_cleanup_is_disabled_and_warns(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path, cleanup="enabled")
    assert engine.generate().success is True

    report = engine.generate(entities=["User"])

    assert report.success is True
    assert (tmp_path / "out" / "post.txt").is_file()
    assert any(item.code == "EG030" for item in report.diagnostics)


def test_per_entity_disables_incremental_cache(tmp_path: Path) -> None:
    PerEntityGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path, incremental=True)
    engine.generate(entities=["User"])
    engine.generate(entities=["User"])

    assert PerEntityGenerator.calls == 2


def test_generator_decorator_accepts_output_scope() -> None:
    @generator(id="decorated", input_formats=None, output_scope="entity")
    def decorated(input: GeneratorInput) -> GenerationResult:
        return GenerationResult(artifacts=[Artifact(path="x.txt", content="x\n")])

    assert decorated.output_scope == "entity"


def test_per_entity_rejects_empty_selection(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path).generate(entities=[])

    assert report.success is False
    assert any(item.code == "EG018" for item in report.diagnostics)


def test_per_entity_intersection_with_generator_input(tmp_path: Path) -> None:
    PerEntityGenerator.last_entities = ()
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, input_entities=("Post",)).generate(entities=["User"])

    assert report.success is True
    assert PerEntityGenerator.last_entities == ()
    assert not (tmp_path / "out" / "user.txt").exists()
    assert not (tmp_path / "out" / "post.txt").exists()


def test_per_entity_check_maps_eg303_to_exit_2(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="model", plugin=ModelGenerator()).check(
        entities=["User"]
    )

    assert report.success is False
    assert report.exit_code == 2
    assert any(item.code == "EG303" for item in report.diagnostics)


def test_per_entity_preserves_input_fingerprint(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path, incremental=True)
    assert engine.generate().success is True
    manifest_path = tmp_path / ".eggpipe" / "manifest.json"
    before = json.loads(manifest_path.read_text(encoding="utf-8"))["locations"][0][
        "input_fingerprint"
    ]
    assert before

    assert engine.generate(entities=["User"]).success is True

    after = json.loads(manifest_path.read_text(encoding="utf-8"))["locations"][0][
        "input_fingerprint"
    ]
    assert after == before


def test_generator_decorator_rejects_invalid_output_scope() -> None:
    with pytest.raises(PluginContractError):
        generator(id="bad-scope", input_formats=None, output_scope="bad")  # type: ignore[arg-type]


def test_per_entity_accepts_single_string(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path).generate(entities="User")  # type: ignore[arg-type]

    assert report.success is True
    assert (tmp_path / "out" / "user.txt").is_file()
