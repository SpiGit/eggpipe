"""CLI smoke tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest
from reference_generator import ReferenceGenerator
from typer.testing import CliRunner

from eggpipe import EntityModelFormat, GenerationResult, GeneratorInput
from eggpipe.cli.main import ReportOptions, _print_report, app
from eggpipe.engine import plugin_loader
from eggpipe.engine.report import EngineReport
from eggpipe.interfaces.generator import GeneratorPlugin

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

MODEL_TWO = """\
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

RULES = """\
version: "1.0"
sources:
  - path: ./model.yaml
    layout: monolith
generators: []
"""


def project(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "model.yaml"
    model.write_text(MODEL, encoding="utf-8")
    rules = tmp_path / ".eggpipe.yaml"
    rules.write_text(RULES, encoding="utf-8")
    return model, rules


def per_entity_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "per_entity_plugin.py"
    plugin.write_text(
        """\
from eggpipe import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin

class PerEntity(GeneratorPlugin):
    id = "per-entity"
    input_formats = None
    output_scope = "entity"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(
            artifacts=[
                Artifact(path=f"{entity.name.lower()}.txt", content=f"{entity.name}\\n")
                for entity in input.model.entities
            ]
        )
""",
        encoding="utf-8",
    )
    return plugin


def test_model_validate(tmp_path: Path) -> None:
    model, _ = project(tmp_path)
    result = CliRunner().invoke(app, ["model", "validate", str(model)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_config_validate(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["config", "validate", "-c", str(rules)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_generate_without_generators(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_generate_check_without_generators(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules), "--check"])
    assert result.exit_code == 0


def test_init(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    result = CliRunner().invoke(app, ["init", str(path), "--layout", "monolith"])
    assert result.exit_code == 0
    assert path.is_file()
    second = CliRunner().invoke(app, ["init", str(path), "--layout", "monolith"])
    assert second.exit_code == 2


def test_format_list() -> None:
    result = CliRunner().invoke(app, ["format", "list"])
    assert result.exit_code == 0
    assert "entity-model" in result.stdout


def test_missing_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["generate", "-c", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 2


def test_model_schema() -> None:
    result = CliRunner().invoke(app, ["model", "schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "ModelDocument"


def test_config_schema() -> None:
    result = CliRunner().invoke(app, ["config", "schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "ProjectConfig"


def test_config_show_has_resolved_paths(tmp_path: Path) -> None:
    model, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["config", "show", "-c", str(rules)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["resolved"]["config_dir"] == str(tmp_path)
    assert data["resolved"]["sources"] == [str(model)]


def test_json_lines_output(capsys: pytest.CaptureFixture[str]) -> None:
    report = EngineReport(success=True, exit_code=0, run_id="run")
    assert (
        _print_report(
            report,
            ReportOptions(
                output_format="json",
                quiet=False,
                verbose=False,
                strict=False,
                ignore=None,
                json_lines=True,
            ),
        )
        == 0
    )
    output = capsys.readouterr().out.strip()
    assert "\n" not in output
    assert json.loads(output)["run_id"] == "run"


def test_clean_requires_yes_in_non_tty(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["clean", "-c", str(rules)])
    assert result.exit_code == 2


class EntryPoint:
    def __init__(self, name: str, value: type[Any]) -> None:
        self.name = name
        self.value = value

    def load(self) -> type[Any]:
        return self.value


def test_generate_with_reference_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules)])
    assert result.exit_code == 0
    assert (tmp_path / "out" / "model.json").is_file()
    assert (tmp_path / ".eggpipe" / "manifest.json").is_file()


def test_generate_incremental_reports_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    runner = CliRunner()
    first = runner.invoke(
        app, ["generate", "-c", str(rules), "--incremental", "--output-format", "json"]
    )
    assert first.exit_code == 0
    second = runner.invoke(
        app, ["generate", "-c", str(rules), "--incremental", "--output-format", "json"]
    )
    assert second.exit_code == 0
    report = json.loads(second.stdout)
    assert report["generators"][0]["status"] == "skipped"
    assert report["artifacts"][0]["action"] == "skip"
    assert report["formats"] == []


def test_generate_incremental_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    monkeypatch.setenv("EGGPIPE_INCREMENTAL", "true")
    runner = CliRunner()
    first = runner.invoke(app, ["generate", "-c", str(rules), "--output-format", "json"])
    assert first.exit_code == 0
    second = runner.invoke(app, ["generate", "-c", str(rules), "--output-format", "json"])
    assert second.exit_code == 0
    report = json.loads(second.stdout)
    assert report["generators"][0]["status"] == "skipped"
    assert report["artifacts"][0]["action"] == "skip"


def test_generate_strict_disables_incremental(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, rules = project(tmp_path)
    model.write_text(MODEL.replace("name: User", "name: user"), encoding="utf-8")
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    runner = CliRunner()
    first = runner.invoke(app, ["generate", "-c", str(rules), "--incremental", "--strict"])
    assert first.exit_code == 1
    second = runner.invoke(app, ["generate", "-c", str(rules), "--incremental", "--strict"])
    assert second.exit_code == 1


def test_generate_json(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules), "--output-format", "json"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["report_version"] == 2
    assert report["success"] is True
    assert report["formats"] == [{"name": "entity-model", "version": "1.0", "entities": 1}]
    assert report["manifest"] == {"manifest_version": 2, "locations": []}
    assert report["stale_locations"] == []
    assert report["artifacts"] == []


def test_generate_with_local_plugin(tmp_path: Path) -> None:
    model, rules = project(tmp_path)
    plugin = tmp_path / "local_plugin.py"
    plugin.write_text(
        """\
from eggpipe import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin

class Local(GeneratorPlugin):
    id = "local"
    name = "Local"
    input_formats = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(artifacts=[Artifact(path="local.txt", content="local\\n")])
""",
        encoding="utf-8",
    )
    rules.write_text(
        RULES.replace(
            "generators: []",
            "generators:\n  - id: local\n    output_dir: ./out",
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["generate", "-c", str(rules), "--plugin", str(plugin)])
    assert result.exit_code == 0
    assert (tmp_path / "out" / "local.txt").read_text(encoding="utf-8") == "local\n"
    assert model.is_file()


def test_init_with_layout(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    result = CliRunner().invoke(
        app,
        ["init", str(path), "--layout", "directory-per-model"],
    )
    assert result.exit_code == 0
    assert "layout: directory-per-model" in path.read_text(encoding="utf-8")


def test_incompatible_format_exits_2(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace(
            "generators: []",
            "generators:\n  - id: no-formats\n    output_dir: ./out",
        ),
        encoding="utf-8",
    )
    plugin = tmp_path / "no_formats.py"
    plugin.write_text(
        """\
from eggpipe import GenerationResult, GeneratorInput, GeneratorPlugin

class NoFormats(GeneratorPlugin):
    id = "no-formats"
    input_formats = set()

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()
""",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--plugin", str(plugin)],
    )
    assert result.exit_code == 2
    assert "EG033" in result.stderr
    assert not (tmp_path / "out").exists()


def test_clean_removes_all_global_locations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    first = CliRunner().invoke(app, ["generate", "-c", str(rules)])
    assert first.exit_code == 0
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out2"),
        encoding="utf-8",
    )
    second = CliRunner().invoke(app, ["generate", "-c", str(rules)])
    assert second.exit_code == 0
    assert "EG051" in second.stderr
    cleaned = CliRunner().invoke(app, ["clean", "--yes", "-c", str(rules)])
    assert cleaned.exit_code == 0
    assert not (tmp_path / "out" / "model.json").exists()
    assert not (tmp_path / "out2" / "model.json").exists()
    assert not (tmp_path / ".eggpipe" / "manifest.json").exists()


def test_strict_and_ignore_only_warnings(tmp_path: Path) -> None:
    model, rules = project(tmp_path)
    model.write_text(
        MODEL.replace("          description: Identifier\n", ""),
        encoding="utf-8",
    )
    normal = CliRunner().invoke(app, ["generate", "-c", str(rules)])
    assert normal.exit_code == 0
    strict = CliRunner().invoke(app, ["generate", "-c", str(rules), "--strict"])
    assert strict.exit_code == 1
    ignored = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--strict", "--ignore", "EG015"],
    )
    assert ignored.exit_code == 0
    error_ignored = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--ignore", "EG004"],
    )
    assert error_ignored.exit_code == 0


def test_format_info() -> None:
    result = CliRunner().invoke(app, ["format", "info", "entity-model"])
    assert result.exit_code == 0
    assert "versions: 1.0" in result.stdout
    assert "schemas: 1.0" in result.stdout


def test_model_schema_for_format() -> None:
    result = CliRunner().invoke(
        app,
        ["model", "schema", "--format", "entity-model"],
    )
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["format"] == "entity-model"
    assert schema["version"] == "1.0"
    assert "full_entity" in schema
    assert "layer_entity" in schema


def test_json_report_v2_action_and_timings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    result = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--output-format", "json"],
    )
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["artifacts"][0]["action"] == "create"
    assert set(report["timings"]) == {
        "discovery_ms",
        "fingerprint_ms",
        "parse_ms",
        "validate_ms",
        "generate_ms",
        "write_ms",
        "total_ms",
    }
    assert report["generators"][0]["status"] == "ok"


def test_generate_per_entity_with_local_plugin(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    plugin = tmp_path / "per_entity_plugin.py"
    plugin.write_text(
        """\
from eggpipe import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin

class PerEntity(GeneratorPlugin):
    id = "per-entity"
    input_formats = None
    output_scope = "entity"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(
            artifacts=[
                Artifact(path=f"{entity.name.lower()}.txt", content=f"{entity.name}\\n")
                for entity in input.model.entities
            ]
        )
""",
        encoding="utf-8",
    )
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: per-entity\n    output_dir: ./out"),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--plugin", str(plugin), "--entity", "User"],
    )
    assert result.exit_code == 0
    assert (tmp_path / "out" / "user.txt").is_file()


def test_generate_per_entity_requires_entity_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, rules = project(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: reference\n    output_dir: ./out"),
        encoding="utf-8",
    )
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules), "--entity", "User"])
    assert result.exit_code == 2
    assert "EG303" in result.stderr


def test_generate_per_entity_unknown_entity(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    plugin = tmp_path / "per_entity_plugin.py"
    plugin.write_text(
        """\
from eggpipe import GenerationResult, GeneratorInput, GeneratorPlugin

class PerEntity(GeneratorPlugin):
    id = "per-entity"
    input_formats = None
    output_scope = "entity"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()
""",
        encoding="utf-8",
    )
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: per-entity\n    output_dir: ./out"),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--plugin", str(plugin), "--entity", "Missing"],
    )
    assert result.exit_code == 1
    assert "EG018" in result.stderr


def test_watch_rejects_entity_option(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["watch", "-c", str(rules), "--entity", "User"])
    assert result.exit_code == 2


def test_gen_info_shows_output_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [EntryPoint("reference", ReferenceGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    result = CliRunner().invoke(app, ["gen", "info", "reference"])
    assert result.exit_code == 0
    assert "output_scope: model" in result.stdout


def test_generate_per_entity_accepts_lists_and_repeats(tmp_path: Path) -> None:
    model, rules = project(tmp_path)
    model.write_text(MODEL_TWO, encoding="utf-8")
    plugin = per_entity_plugin(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: per-entity\n    output_dir: ./out"),
        encoding="utf-8",
    )
    runner = CliRunner()
    first = runner.invoke(
        app,
        ["generate", "-c", str(rules), "--plugin", str(plugin), "--entity", "User"],
    )
    assert first.exit_code == 0
    assert (tmp_path / "out" / "user.txt").is_file()
    assert not (tmp_path / "out" / "post.txt").exists()

    second = runner.invoke(
        app,
        [
            "generate",
            "-c",
            str(rules),
            "--plugin",
            str(plugin),
            "--entity",
            "User, Post",
            "--entity",
            "User",
        ],
    )
    assert second.exit_code == 0
    assert (tmp_path / "out" / "post.txt").is_file()


@pytest.mark.parametrize("value", ["", ",", " , "])
def test_generate_empty_entity_exits_2(tmp_path: Path, value: str) -> None:
    _, rules = project(tmp_path)
    plugin = per_entity_plugin(tmp_path)
    rules.write_text(
        RULES.replace("generators: []", "generators:\n  - id: per-entity\n    output_dir: ./out"),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["generate", "-c", str(rules), "--plugin", str(plugin), "--entity", value],
    )
    assert result.exit_code == 2


def _patch_entry_points(monkeypatch: pytest.MonkeyPatch, entries: list[EntryPoint]) -> None:
    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        del group
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)


class DemoModelFormat(EntityModelFormat):
    """Format plugin for `format info` tests: extends entity-model."""

    format_names: ClassVar[list[str]] = ["demo-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}


class BrokenGenerator(GeneratorPlugin):
    """Generator with an invalid id: triggers a coded plugin issue."""

    id = "Broken"
    input_formats = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


def test_gen_info_shows_plugin_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [EntryPoint("reference", ReferenceGenerator)])
    result = CliRunner().invoke(app, ["gen", "info", "reference"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[:6] == [
        "id: reference",
        "name: Reference Generator",
        "api_version: 1",
        "input_formats: entity-model",
        "output_scope: model",
        "entry point group: eggpipe.generators",
    ]
    assert lines[6:] == ["module: reference_generator", "class: ReferenceGenerator"]


def test_gen_info_unknown_suggests(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [EntryPoint("reference", ReferenceGenerator)])
    result = CliRunner().invoke(app, ["gen", "info", "referense"])
    assert result.exit_code == 2
    assert "error: unknown generator: referense" in result.stderr
    assert "did you mean: reference" in result.stderr
    assert "available generators: reference" in result.stderr


def test_format_info_shows_plugin_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [])
    result = CliRunner().invoke(app, ["format", "info", "entity-model"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[:5] == [
        "name: entity-model",
        "versions: 1.0",
        "extends: -",
        "primitive_types: bigint,boolean,date,datetime,float,integer,json,string,text,uuid",
        "schemas: 1.0",
    ]
    assert lines[5:] == [
        "api_version: 1",
        "module: eggpipe.interfaces.formats",
        "class: EntityModelFormat",
        "base_versions: -",
    ]


def test_format_info_shows_base_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [EntryPoint("demo-model", DemoModelFormat)])
    result = CliRunner().invoke(app, ["format", "info", "demo-model"])
    assert result.exit_code == 0
    assert "extends: entity-model" in result.stdout
    assert "class: DemoModelFormat" in result.stdout
    assert "base_versions: 1.0->1.0" in result.stdout


def test_format_info_unknown_suggests(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [])
    result = CliRunner().invoke(app, ["format", "info", "entity-modell"])
    assert result.exit_code == 2
    assert "error: unknown format: entity-modell" in result.stderr
    assert "did you mean: entity-model" in result.stderr
    assert "available formats: entity-model" in result.stderr


def test_plugin_issue_warning_includes_code(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, [EntryPoint("broken", BrokenGenerator)])
    result = CliRunner().invoke(app, ["gen", "list", "--all"])
    assert result.exit_code == 0
    assert (
        "warning: broken: EG301: test_cli:BrokenGenerator: generator id 'Broken'" in result.stderr
    )
    assert result.stderr.count("EG301") == 1
