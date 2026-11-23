"""Tests for opt-in incremental generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typing_extensions import override

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    EntityModelFormat,
    FormatRegistry,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    Parser,
    ProjectConfig,
    SourceConfig,
)
from eggpipe.config.project_config import DiagnosticsConfig

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


class DependencyFormat(EntityModelFormat):
    format_names: ClassVar[list[str]] = ["dependency-model"]
    __version__ = "1"

    @override
    def input_paths(self, raw: dict[str, Any], base_path: Path) -> list[Path] | None:
        return [base_path / "extra.txt"]


class NoDependencyFormat(EntityModelFormat):
    format_names: ClassVar[list[str]] = ["no-dependency-model"]

    @override
    def input_paths(self, raw: dict[str, Any], base_path: Path) -> list[Path] | None:
        return None


class UnsafeDependencyFormat(EntityModelFormat):
    format_names: ClassVar[list[str]] = ["unsafe-model"]

    @override
    def input_paths(self, raw: dict[str, Any], base_path: Path) -> list[Path] | None:
        return [Path("../outside.txt")]


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
    clean: bool = False,
    allow_outside_imports: bool = False,
    stale_dates: bool = False,
    formats: FormatRegistry | None = None,
    source: Path = Path("model.yaml"),
) -> Engine:
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=source, layout="monolith"),),
        generators=(GeneratorConfig(id="counting", output_dir=Path("out")),),
        diagnostics=DiagnosticsConfig(stale_dates=stale_dates),
    )
    return Engine(
        AppConfig(
            incremental=incremental,
            force=force,
            clean=clean,
            allow_outside_imports=allow_outside_imports,
        ),
        rules,
        config_dir=tmp_path,
        generators={"counting": CountingGenerator()},
        formats=formats,
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
    assert second.formats == []
    assert second.timings["parse_ms"] == 0
    assert second.timings["validate_ms"] == 0
    assert second.timings["generate_ms"] == 0
    assert second.timings["write_ms"] == 0
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


def test_incremental_is_disabled_with_stale_dates(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path, stale_dates=True).generate()
    make_engine(tmp_path, stale_dates=True).generate()
    assert CountingGenerator.calls == 2


def test_incremental_is_disabled_with_clean(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    make_engine(tmp_path, clean=True).generate()
    assert CountingGenerator.calls == 2


def test_incremental_invalidates_on_plugin_version(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    original = CountingGenerator.__version__
    try:
        CountingGenerator.__version__ = "2"
        make_engine(tmp_path).generate()
    finally:
        CountingGenerator.__version__ = original
    assert CountingGenerator.calls == 2


def test_incremental_ignores_manifest_without_fingerprint(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    manifest_path = tmp_path / ".eggpipe" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["locations"][0].pop("input_fingerprint")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_ignores_unrelated_yaml(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    (tmp_path / "notes.yaml").write_text("key: value\n", encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 1


def test_incremental_invalidates_on_resource_import(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    template = tmp_path / "card.html"
    template.write_text("<p>one</p>\n", encoding="utf-8")
    model = MODEL.replace(
        "model:\n",
        "model:\n  imports:\n    - path: ./card.html\n      as: card\n",
    )
    (tmp_path / "model.yaml").write_text(model, encoding="utf-8")
    make_engine(tmp_path).generate()
    template.write_text("<p>two</p>\n", encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_requires_matching_locations(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    manifest_path = tmp_path / ".eggpipe" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["locations"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_plan_uses_cache(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    plan = make_engine(tmp_path).build()
    assert CountingGenerator.calls == 1
    assert plan.generators[0].status == "skipped"
    assert plan.artifacts[0].action == "skip"


def test_incremental_ignores_invalid_unrelated_yaml(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    (tmp_path / "broken.yaml").write_bytes(b"\xff\xfe\x00")
    make_engine(tmp_path).generate()
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 1


def test_incremental_disables_cache_on_unsafe_input_path(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(
        MODEL.replace("format: entity-model", "format: unsafe-model"),
        encoding="utf-8",
    )
    registry = FormatRegistry()
    registry.register(UnsafeDependencyFormat())
    make_engine(tmp_path, formats=registry).generate()
    make_engine(tmp_path, formats=registry).generate()
    assert CountingGenerator.calls == 2


def test_incremental_invalidates_on_format_input_paths(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    extra = tmp_path / "extra.txt"
    extra.write_text("one\n", encoding="utf-8")
    (tmp_path / "model.yaml").write_text(
        MODEL.replace("format: entity-model", "format: dependency-model"),
        encoding="utf-8",
    )
    registry = FormatRegistry()
    registry.register(DependencyFormat())
    make_engine(tmp_path, formats=registry).generate()
    extra.write_text("two\n", encoding="utf-8")
    make_engine(tmp_path, formats=registry).generate()
    assert CountingGenerator.calls == 2


def test_incremental_disabled_when_format_has_no_dependency_contract(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(
        MODEL.replace("format: entity-model", "format: no-dependency-model"),
        encoding="utf-8",
    )
    registry = FormatRegistry()
    registry.register(NoDependencyFormat())
    make_engine(tmp_path, formats=registry).generate()
    make_engine(tmp_path, formats=registry).generate()
    assert CountingGenerator.calls == 2


def test_incremental_requires_exact_locations(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    manifest_path = tmp_path / ".eggpipe" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ghost = dict(manifest["locations"][0])
    ghost["generator"] = "ghost"
    ghost["output_dir"] = "out-ghost"
    manifest["locations"].append(ghost)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_ignores_escaping_manifest_path(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    manifest_path = tmp_path / ".eggpipe" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["locations"][0]["artifacts"][0]["path"] = "../escape.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2
    assert not (tmp_path / "escape.txt").exists()


def test_incremental_disables_cache_on_corrupt_manifest(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    (tmp_path / ".eggpipe" / "manifest.json").write_text("{broken", encoding="utf-8")
    make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 2


def test_incremental_logs_disable_reason(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "model.yaml").write_text(MODEL, encoding="utf-8")
    make_engine(tmp_path).generate()
    with caplog.at_level(logging.DEBUG, logger="eggpipe.engine.engine"):
        make_engine(tmp_path, force=True).generate()
    assert any("incremental cache disabled" in item.getMessage() for item in caplog.records)


def test_incremental_hits_for_format_inputs_in_nested_dir(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    models = tmp_path / "models"
    models.mkdir()
    (models / "model.yaml").write_text(
        MODEL.replace("format: entity-model", "format: dependency-model"),
        encoding="utf-8",
    )
    (models / "extra.txt").write_text("one\n", encoding="utf-8")
    registry = FormatRegistry()
    registry.register(DependencyFormat())
    make_engine(tmp_path, source=Path("models/model.yaml"), formats=registry).generate()
    second = make_engine(tmp_path, source=Path("models/model.yaml"), formats=registry).generate()
    assert CountingGenerator.calls == 1
    assert second.generators[0].status == "skipped"


def test_incremental_hits_with_yaml_import(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "base.yaml").write_text(
        "format: entity-model\nversion: '1.0'\nmodel: {}\n",
        encoding="utf-8",
    )
    model = MODEL.replace(
        "model:\n",
        "model:\n  imports:\n    - path: ./base.yaml\n      as: base\n",
    )
    (tmp_path / "model.yaml").write_text(model, encoding="utf-8")
    make_engine(tmp_path).generate()
    second = make_engine(tmp_path).generate()
    assert CountingGenerator.calls == 1
    assert second.generators[0].status == "skipped"


def test_incremental_invalidates_on_format_plugin_version(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    (tmp_path / "extra.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "model.yaml").write_text(
        MODEL.replace("format: entity-model", "format: dependency-model"),
        encoding="utf-8",
    )
    registry = FormatRegistry()
    registry.register(DependencyFormat())
    make_engine(tmp_path, formats=registry).generate()
    original = DependencyFormat.__version__
    try:
        DependencyFormat.__version__ = "2"
        make_engine(tmp_path, formats=registry).generate()
    finally:
        DependencyFormat.__version__ = original
    assert CountingGenerator.calls == 2


DIR_MODEL_ALPHA = MODEL.replace("User", "Alpha")
DIR_MODEL_BETA = MODEL.replace("User", "Beta")


def make_dir_engine(tmp_path: Path, *, incremental: bool = True, force: bool = False) -> Engine:
    rules = ProjectConfig(
        version="1.0",
        sources=(SourceConfig(path=Path("model"), layout="file-per-model", files=("*.yaml",)),),
        generators=(GeneratorConfig(id="counting", output_dir=Path("out")),),
    )
    return Engine(
        AppConfig(incremental=incremental, force=force),
        rules,
        config_dir=tmp_path,
        generators={"counting": CountingGenerator()},
    )


def write_dir_model(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "model").mkdir()
    first = tmp_path / "model/a.yaml"
    second = tmp_path / "model/b.yaml"
    first.write_text(DIR_MODEL_ALPHA, encoding="utf-8")
    second.write_text(DIR_MODEL_BETA, encoding="utf-8")
    return first, second


def count_parses(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    original = Parser.parse_document

    def wrapper(self: Parser, path: Path) -> Any:
        calls.append(path)
        return original(self, path)

    monkeypatch.setattr(Parser, "parse_document", wrapper)
    return calls


def test_l2_cache_skips_parsing_unchanged_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    CountingGenerator.calls = 0
    write_dir_model(tmp_path)
    make_dir_engine(tmp_path).generate()

    calls = count_parses(monkeypatch)
    second = make_dir_engine(tmp_path).generate()

    assert second.success is True
    assert second.generators[0].status == "skipped"
    assert second.timings["parse_ms"] == 0
    assert calls == []
    assert (tmp_path / ".eggpipe" / "cache" / "meta.json").is_file()


def test_l2_cache_parses_only_changed_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    CountingGenerator.calls = 0
    first, _ = write_dir_model(tmp_path)
    make_dir_engine(tmp_path).generate()
    first.write_text(DIR_MODEL_ALPHA + "# changed\n", encoding="utf-8")

    calls = count_parses(monkeypatch)
    second = make_dir_engine(tmp_path).generate()

    assert second.success is True
    assert CountingGenerator.calls == 2
    assert calls == [first.resolve()]


def test_l2_cache_hits_when_file_is_renamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    CountingGenerator.calls = 0
    _, second = write_dir_model(tmp_path)
    make_dir_engine(tmp_path).generate()
    second.rename(tmp_path / "model/c.yaml")

    calls = count_parses(monkeypatch)
    report = make_dir_engine(tmp_path).generate()

    assert report.success is True
    assert calls == []


def test_l2_cache_recovers_from_corruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    CountingGenerator.calls = 0
    write_dir_model(tmp_path)
    make_dir_engine(tmp_path).generate()
    (tmp_path / ".eggpipe" / "cache" / "meta.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "model" / "a.yaml").write_text(DIR_MODEL_ALPHA + "# changed\n", encoding="utf-8")

    calls = count_parses(monkeypatch)
    report = make_dir_engine(tmp_path).generate()

    assert report.success is True
    assert len(calls) == 2
    fresh = count_parses(monkeypatch)
    make_dir_engine(tmp_path).generate()
    assert fresh == []


def test_l2_cache_is_not_written_by_plan(tmp_path: Path) -> None:
    write_dir_model(tmp_path)

    report = make_dir_engine(tmp_path).build()

    assert report.success is True
    assert not (tmp_path / ".eggpipe" / "cache").exists()


def test_l2_cache_is_not_used_for_entities(tmp_path: Path) -> None:
    CountingGenerator.calls = 0
    write_dir_model(tmp_path)

    make_dir_engine(tmp_path).generate(entities=["Alpha"])

    assert not (tmp_path / ".eggpipe" / "cache").exists()


def test_l2_cache_is_not_written_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    CountingGenerator.calls = 0
    write_dir_model(tmp_path)
    make_dir_engine(tmp_path).generate()
    calls = count_parses(monkeypatch)

    make_dir_engine(tmp_path, force=True).generate()

    assert len(calls) == 2
