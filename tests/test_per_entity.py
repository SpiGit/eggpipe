"""Tests for per-entity generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Literal

import pytest
from typing_extensions import override

from eggpipe import (
    AppConfig,
    Artifact,
    ConfigValidationError,
    Diagnostic,
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


EMPTY_MODEL = """\
format: entity-model
version: "1.0"
model:
  entities: []
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


class EntityAllGenerator(GeneratorPlugin):
    id = "entity-all"
    name = "Entity all"
    input_formats: ClassVar[set[str] | None] = None
    output_scope: ClassVar[Literal["entity"]] = "entity"
    __version__ = "1"
    calls: ClassVar[list[tuple[str, ...]]] = []

    def generate(self, input: GeneratorInput) -> GenerationResult:
        names = tuple(entity.name for entity in input.model.entities)
        type(self).calls.append(names)
        return GenerationResult(
            artifacts=[
                Artifact(path=f"{entity.name.lower()}.txt", content=f"{entity.name}\n")
                for entity in input.model.entities
            ]
        )


class EntityAllGeneratorTwo(EntityAllGenerator):
    id = "entity-all-2"
    name = "Entity all 2"


class FailingEntityGenerator(EntityAllGenerator):
    id = "failing-entity"
    name = "Failing entity"

    @override
    def generate(self, input: GeneratorInput) -> GenerationResult:
        result = super().generate(input)
        if any(entity.name == "Post" for entity in input.model.entities):
            return result.model_copy(
                update={
                    "errors": [
                        Diagnostic(
                            level="error",
                            code="EG300",
                            message="Post failed",
                        )
                    ]
                }
            )
        if any(entity.name == "User" for entity in input.model.entities):
            return result.model_copy(
                update={
                    "warnings": [
                        Diagnostic(
                            level="warning",
                            code="EG300",
                            message="User warning",
                        )
                    ]
                }
            )
        return result


class BrokenConfigGenerator(EntityAllGenerator):
    id = "broken-config"
    name = "Broken config"
    calls: ClassVar[list[tuple[str, ...]]] = []

    @override
    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        raise RuntimeError("broken config")

    @override
    def generate(self, input: GeneratorInput) -> GenerationResult:
        return super().generate(input)


class DuplicatePathGenerator(EntityAllGenerator):
    id = "duplicate-path"
    name = "Duplicate path"

    @override
    def generate(self, input: GeneratorInput) -> GenerationResult:
        type(self).calls.append(tuple(entity.name for entity in input.model.entities))
        return GenerationResult(artifacts=[Artifact(path="same.txt", content="same\n")])


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


def test_entity_all_calls_generator_once_per_entity(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path, generator_id="entity-all", plugin=EntityAllGenerator())

    report = engine.generate(entity_all=True)

    assert report.success is True
    assert EntityAllGenerator.calls == [("User",), ("Post",)]
    assert (tmp_path / "out" / "user.txt").is_file()
    assert (tmp_path / "out" / "post.txt").is_file()
    assert len(report.generators) == 1
    assert report.generators[0].status == "ok"
    manifest = json.loads((tmp_path / ".eggpipe" / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["locations"][0]["artifacts"]}
    assert paths == {"user.txt", "post.txt"}


def test_entity_all_respects_generator_input(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(
        tmp_path,
        generator_id="entity-all",
        plugin=EntityAllGenerator(),
        input_entities=("Post",),
    )

    report = engine.generate(entity_all=True)

    assert report.success is True
    assert EntityAllGenerator.calls == [("Post",)]
    assert not (tmp_path / "out" / "user.txt").exists()
    assert (tmp_path / "out" / "post.txt").is_file()


def test_entity_all_requires_entity_scope(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="model", plugin=ModelGenerator()).generate(
        entity_all=True
    )

    assert report.success is False
    assert report.exit_code == 2
    assert any(item.code == "EG303" for item in report.diagnostics)
    assert not (tmp_path / "out" / "all.txt").exists()


def test_entity_all_rejects_entities_argument(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        make_engine(tmp_path).generate(entities=["User"], entity_all=True)


def test_entity_all_rejects_empty_model(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(EMPTY_MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="entity-all", plugin=EntityAllGenerator()).generate(
        entity_all=True
    )

    assert report.success is False
    assert report.exit_code == 1
    assert any(item.code == "EG018" for item in report.diagnostics)
    assert not (tmp_path / "out").exists()


def test_entity_all_cleanup_is_disabled_and_warns(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(
        tmp_path,
        generator_id="entity-all",
        plugin=EntityAllGenerator(),
        cleanup="enabled",
    )
    assert engine.generate().success is True

    report = engine.generate(entity_all=True)

    assert report.success is True
    assert (tmp_path / "out" / "user.txt").is_file()
    assert (tmp_path / "out" / "post.txt").is_file()
    assert any(item.code == "EG030" for item in report.diagnostics)


def test_entity_all_disables_incremental_cache(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(
        tmp_path, generator_id="entity-all", plugin=EntityAllGenerator(), incremental=True
    )
    engine.generate(entity_all=True)
    engine.generate(entity_all=True)

    assert len(EntityAllGenerator.calls) == 4


def test_entity_all_rejects_duplicate_paths(tmp_path: Path) -> None:
    DuplicatePathGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(
        tmp_path, generator_id="duplicate-path", plugin=DuplicatePathGenerator()
    ).generate(entity_all=True)

    assert report.success is False
    assert any(item.code == "EG042" for item in report.diagnostics)
    assert not (tmp_path / "out" / "same.txt").exists()


def test_entity_all_continues_after_entity_error_and_writes_nothing(tmp_path: Path) -> None:
    FailingEntityGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(
        tmp_path, generator_id="failing-entity", plugin=FailingEntityGenerator()
    ).generate(entity_all=True)

    assert report.success is False
    assert FailingEntityGenerator.calls == [("User",), ("Post",)]
    assert any(
        item.code == "EG300"
        and item.level == "error"
        and item.location is not None
        and item.location.entity == "Post"
        for item in report.diagnostics
    )
    assert any(
        item.code == "EG300"
        and item.level == "warning"
        and item.location is not None
        and item.location.entity == "User"
        for item in report.diagnostics
    )
    assert not (tmp_path / "out" / "user.txt").exists()
    assert not (tmp_path / "out" / "post.txt").exists()


def test_entity_all_aggregates_multiple_generators(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml"), layout="monolith"),),
        generators=(
            GeneratorConfig(id="entity-all", output_dir=Path("out-a")),
            GeneratorConfig(id="entity-all-2", output_dir=Path("out-b")),
        ),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={
            "entity-all": EntityAllGenerator(),
            "entity-all-2": EntityAllGeneratorTwo(),
        },
    )

    report = engine.generate(entity_all=True)

    assert report.success is True
    assert [item.id for item in report.generators] == ["entity-all", "entity-all-2"]
    assert (tmp_path / "out-a" / "user.txt").is_file()
    assert (tmp_path / "out-a" / "post.txt").is_file()
    assert (tmp_path / "out-b" / "user.txt").is_file()
    assert (tmp_path / "out-b" / "post.txt").is_file()


def test_entity_all_build_does_not_write(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="entity-all", plugin=EntityAllGenerator()).build(
        entity_all=True
    )

    assert report.success is True
    assert EntityAllGenerator.calls == [("User",), ("Post",)]
    assert not (tmp_path / "out").exists()


def test_entity_all_validate_config_failure_is_error(tmp_path: Path) -> None:
    BrokenConfigGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(
        tmp_path, generator_id="broken-config", plugin=BrokenConfigGenerator()
    ).generate(entity_all=True)

    assert report.success is False
    assert report.exit_code == 1
    assert report.generators[0].status == "error"
    assert any(item.code == "EG300" for item in report.diagnostics)
    assert BrokenConfigGenerator.calls == []
    assert not (tmp_path / "out").exists()


def test_entity_all_check_requires_entity_scope(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(tmp_path, generator_id="model", plugin=ModelGenerator()).check(
        entity_all=True
    )

    assert report.success is False
    assert report.exit_code == 2
    assert any(item.code == "EG303" for item in report.diagnostics)


def test_entity_all_check_reports_existing_artifacts(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    engine = make_engine(tmp_path, generator_id="entity-all", plugin=EntityAllGenerator())
    assert engine.generate(entity_all=True).success is True

    report = engine.check(entity_all=True)

    assert report.success is True
    assert report.exit_code == 0
    assert {item.path for item in report.artifacts} == {"user.txt", "post.txt"}


def test_entity_all_rejects_unknown_generator_input(tmp_path: Path) -> None:
    EntityAllGenerator.calls = []
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    report = make_engine(
        tmp_path,
        generator_id="entity-all",
        plugin=EntityAllGenerator(),
        input_entities=("Missing",),
    ).generate(entity_all=True)

    assert report.success is False
    assert any(item.code == "EG018" for item in report.diagnostics)
    assert EntityAllGenerator.calls == []
