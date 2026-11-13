"""Тесты model units, слоёв и ресурсов."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from eggpipe import (
    PRIMITIVE_TYPES,
    AppConfig,
    Artifact,
    Engine,
    Entity,
    EntityModelFormat,
    FormatRegistry,
    FormatSchema,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    GeneratorRules,
    Parser,
    SourceConfig,
)
from eggpipe.config.generator_rules import InputSlice, ModelOverride, ResourceConfig
from eggpipe.core.discovery import discover_sources
from eggpipe.core.layers import merge_model_layers
from eggpipe.core.model import LayerEntity
from eggpipe.utils.exceptions import DocumentError

BASE = """\
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
        - name: name
          type: string
"""

DELTA = """\
format: postgres-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: email
          type: string
"""


class PostgresFormat(EntityModelFormat):
    format_names: ClassVar[list[str]] = ["postgres-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}
    primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)
    schemas: ClassVar[dict[str, FormatSchema]] = {
        "1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity)
    }


class Capture(GeneratorPlugin):
    id = "capture"
    name = "Capture"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        entity = input.model.entity("User")
        fields = ",".join(field.name for field in entity.fields)
        layers = len(entity.layer_sources)
        content = f"{entity.format}|{fields}|{layers}|{','.join(sorted(input.context.imports))}\n"
        return GenerationResult(artifacts=[Artifact(path="result.txt", content=content)])


def write_model(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def registry() -> FormatRegistry:
    result = FormatRegistry()
    result.register(PostgresFormat())
    return result


def parse(path: Path, formats: FormatRegistry | None = None) -> Any:
    return Parser(formats or registry()).parse_document(path)


def test_merge_layers_and_provenance(tmp_path: Path) -> None:
    base_path = write_model(tmp_path / "user" / "base.yaml", BASE)
    delta_path = write_model(tmp_path / "user" / "postgres.yaml", DELTA)
    result = merge_model_layers(
        [parse(base_path), parse(delta_path)],
        registry(),
    )
    entity = result.document.model.entity("User")
    assert [field.name for field in entity.fields] == ["id", "name", "email"]
    assert entity.format == "postgres-model"
    assert entity.format_version == "1.0"
    assert entity.source == base_path
    assert entity.layer_sources == (base_path, delta_path)
    assert entity.fields[0].source == base_path
    assert entity.fields[2].source == delta_path
    assert result.diagnostics == []


def test_empty_delta_warns(tmp_path: Path) -> None:
    base_path = write_model(tmp_path / "user" / "base.yaml", BASE)
    delta_path = write_model(
        tmp_path / "user" / "postgres.yaml",
        DELTA.replace(
            "      fields:\n        - name: email\n          type: string\n",
            "      fields: []\n",
        ),
    )
    result = merge_model_layers([parse(base_path), parse(delta_path)], registry())
    assert [item.code for item in result.diagnostics] == ["MG035"]


def test_layer_must_have_one_entity(tmp_path: Path) -> None:
    path = write_model(
        tmp_path / "user" / "base.yaml",
        BASE.replace("    - name: User\n", "    - name: Other\n    - name: User\n"),
    )
    with pytest.raises(DocumentError) as caught:
        merge_model_layers([parse(path)], registry())
    assert caught.value.code == "MG031"


def test_duplicate_and_unrelated_formats(tmp_path: Path) -> None:
    first = write_model(tmp_path / "user" / "a.yaml", BASE)
    second = write_model(tmp_path / "user" / "b.yaml", BASE)
    with pytest.raises(DocumentError) as duplicate:
        merge_model_layers([parse(first), parse(second)], registry())
    assert duplicate.value.code == "MG029"

    class OtherFormat(EntityModelFormat):
        format_names: ClassVar[list[str]] = ["other-model"]
        supported_versions: ClassVar[list[str]] = ["1.0"]
        extends: ClassVar[str | None] = "entity-model"
        base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}
        primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity)
        }

    formats = registry()
    formats.register(OtherFormat())
    other = write_model(
        tmp_path / "user" / "c.yaml",
        BASE.replace("entity-model", "other-model"),
    )
    with pytest.raises(DocumentError) as unrelated:
        merge_model_layers(
            [
                parse(other, formats),
                parse(write_model(tmp_path / "user" / "d.yaml", DELTA), formats),
            ],
            formats,
        )
    assert unrelated.value.code == "MG029"


def test_directory_layout_through_engine(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "user" / "base.yaml", BASE)
    write_model(tmp_path / "models" / "user" / "postgres.yaml", DELTA)
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="directory-per-model",
                model_dirs=("*",),
                files=("*.yaml",),
            ),
        ),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"capture": Capture()},
        formats=registry(),
    )
    report = engine.generate()
    assert report.success is True
    assert (tmp_path / "out" / "result.txt").read_text(encoding="utf-8") == (
        "postgres-model|id,name,email|2|\n"
    )


def test_discovery_resources_and_overrides(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "user" / "base.yaml", BASE)
    write_model(tmp_path / "models" / "user" / "postgres.yaml", DELTA)
    write_model(tmp_path / "models" / "user" / "resources" / "avatar.svg", "<svg/>")
    write_model(tmp_path / "shared" / "seed.json", "{}")
    rules = GeneratorRules(
        version="1.0",
        resources=(ResourceConfig(path=Path("shared")),),
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="directory-per-model",
                model_dirs=("*",),
                files=("*.yaml",),
                models={"user": ModelOverride(resources=(ResourceConfig(path=Path("resources")),))},
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    assert set(discovered.resources) == {"shared/seed", "user/resources/avatar"}
    assert discovered.diagnostics == []


def test_discovery_empty_dir_and_unknown_override(tmp_path: Path) -> None:
    (tmp_path / "models" / "empty").mkdir(parents=True)
    write_model(tmp_path / "models" / "user" / "base.yaml", BASE)
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="directory-per-model",
                model_dirs=("*",),
                files=("*.yaml",),
                models={"missing": ModelOverride(files=("*.yaml",))},
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    codes = {item.code for item in discovered.diagnostics}
    assert "MG027" in codes
    assert "MG037" in codes


def test_resource_collision_and_overlap(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "user" / "base.yaml", BASE)
    write_model(tmp_path / "models" / "user" / "asset.txt", "x")
    rules = GeneratorRules(
        version="1.0",
        resources=(
            ResourceConfig.model_validate({"path": "models/user/asset.txt", "as": "user/asset"}),
        ),
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="directory-per-model",
                model_dirs=("user",),
                files=("*.yaml", "asset.txt"),
                models={"user": ModelOverride(resources=(ResourceConfig(path=Path("asset.txt")),))},
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    codes = {item.code for item in discovered.diagnostics}
    assert "MG032" in codes
    assert "MG038" in codes


def test_source_input_applies_to_whole_source(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "a.yaml", BASE)
    write_model(
        tmp_path / "models" / "b.yaml",
        BASE.replace("name: User", "name: Other"),
    )
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="file-per-model",
                files=("*.yaml",),
                input=InputSlice(entities=("Other",)),
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    assert len(discovered.groups) == 1
    assert len(discovered.groups[0].units or ()) == 2


def test_layer_version_must_match_base_version(tmp_path: Path) -> None:
    class MultiBase(EntityModelFormat):
        format_names: ClassVar[list[str]] = ["multi-base"]
        supported_versions: ClassVar[list[str]] = ["1.0", "2.0"]
        primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity),
            "2.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity),
        }

    class MultiChild(EntityModelFormat):
        format_names: ClassVar[list[str]] = ["multi-child"]
        supported_versions: ClassVar[list[str]] = ["1.0"]
        extends: ClassVar[str | None] = "multi-base"
        base_versions: ClassVar[dict[str, str]] = {"1.0": "2.0"}
        primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)
        schemas: ClassVar[dict[str, FormatSchema]] = {
            "1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity)
        }

    formats = FormatRegistry()
    formats.register(MultiBase())
    formats.register(MultiChild())
    base_path = write_model(
        tmp_path / "user" / "base.yaml",
        BASE.replace("entity-model", "multi-base").replace('"1.0"', '"1.0"'),
    )
    child_path = write_model(
        tmp_path / "user" / "child.yaml",
        DELTA.replace("postgres-model", "multi-child"),
    )
    with pytest.raises(DocumentError) as caught:
        merge_model_layers([parse(base_path, formats), parse(child_path, formats)], formats)
    assert caught.value.code == "MG034"


def test_file_per_model_requires_one_entity(tmp_path: Path) -> None:
    write_model(
        tmp_path / "models" / "users.yaml",
        BASE.replace("    - name: User\n", "    - name: Other\n    - name: User\n"),
    )
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="file-per-model",
                files=("*.yaml",),
            ),
        ),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={},
        formats=registry(),
    )
    report = engine.build()
    assert report.success is False
    assert "MG031" in {item.code for item in report.diagnostics}


def test_glob_without_matches_warns(tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="file-per-model",
                files=("*.yaml",),
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    assert "MG036" in {item.code for item in discovered.diagnostics}


def test_resource_boundary_and_glob_alias(tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    outside = write_model(tmp_path.parent / "shared" / "seed.json", "{}")
    rules = GeneratorRules(
        version="1.0",
        resources=(ResourceConfig(path=Path(f"../shared/{outside.name}")),),
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="file-per-model",
                files=("*.yaml",),
            ),
        ),
    )
    blocked = discover_sources(rules, tmp_path)
    assert "MG022" in {item.code for item in blocked.diagnostics}
    allowed = discover_sources(rules, tmp_path, allow_outside=True)
    assert "MG022" not in {item.code for item in allowed.diagnostics}

    write_model(tmp_path / "docs" / "a.txt", "a")
    write_model(tmp_path / "docs" / "b.txt", "b")
    alias_rules = GeneratorRules(
        version="1.0",
        resources=(ResourceConfig.model_validate({"path": "docs/*.txt", "as": "doc"}),),
    )
    alias = discover_sources(alias_rules, tmp_path)
    assert "MG032" in {item.code for item in alias.diagnostics}


def test_engine_passes_resources_to_context(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "user" / "base.yaml", BASE)
    write_model(tmp_path / "shared" / "seed.json", "{}")
    rules = GeneratorRules(
        version="1.0",
        resources=(ResourceConfig(path=Path("shared")),),
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="directory-per-model",
                model_dirs=("user",),
                files=("*.yaml",),
            ),
        ),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"capture": Capture()},
        formats=registry(),
    )
    report = engine.generate()
    assert report.success is True
    assert (tmp_path / "out" / "result.txt").read_text(encoding="utf-8") == (
        "entity-model|id,name|1|shared/seed\n"
    )


def test_non_model_yaml_reports_mg023(tmp_path: Path) -> None:
    write_model(tmp_path / "models" / "user.yaml", BASE)
    write_model(tmp_path / "models" / "notes.yaml", "title: notes\n")
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                layout="file-per-model",
                files=("*.yaml",),
            ),
        ),
    )
    discovered = discover_sources(rules, tmp_path)
    assert "MG023" in {item.code for item in discovered.diagnostics}
    assert [path.name for path in discovered.paths] == ["user.yaml"]
