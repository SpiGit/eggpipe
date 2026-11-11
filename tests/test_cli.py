"""Smoke-тесты CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reference_generator import ReferenceGenerator
from typer.testing import CliRunner

from metadata_generator.cli.main import app
from metadata_generator.engine import plugin_loader
from metadata_generator.interfaces.generator import GeneratorPlugin

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

RULES = """\
version: "1.0"
sources:
  - path: ./model.yaml
generators: []
"""


def project(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "model.yaml"
    model.write_text(MODEL, encoding="utf-8")
    rules = tmp_path / ".mg.yaml"
    rules.write_text(RULES, encoding="utf-8")
    return model, rules


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
    path = tmp_path / ".mg.yaml"
    result = CliRunner().invoke(app, ["init", str(path)])
    assert result.exit_code == 0
    assert path.is_file()
    second = CliRunner().invoke(app, ["init", str(path)])
    assert second.exit_code == 2


def test_format_list() -> None:
    result = CliRunner().invoke(app, ["format", "list"])
    assert result.exit_code == 0
    assert "entity-model" in result.stdout


def test_missing_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["generate", "-c", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 2


class EntryPoint:
    def __init__(self, name: str, value: type[GeneratorPlugin]) -> None:
        self.name = name
        self.value = value

    def load(self) -> type[GeneratorPlugin]:
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
    assert (tmp_path / "out" / ".mg" / "manifests" / "reference.json").is_file()


def test_generate_json(tmp_path: Path) -> None:
    _, rules = project(tmp_path)
    result = CliRunner().invoke(app, ["generate", "-c", str(rules), "--output-format", "json"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["report_version"] == 1
    assert report["success"] is True


def test_generate_with_local_plugin(tmp_path: Path) -> None:
    model, rules = project(tmp_path)
    plugin = tmp_path / "local_plugin.py"
    plugin.write_text(
        """\
from metadata_generator import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin

class Local(GeneratorPlugin):
    id = "local"
    name = "Local"

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
