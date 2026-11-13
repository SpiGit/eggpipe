"""Tests for .eggpipe.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from eggpipe import (
    ConfigValidationError,
    ProjectConfigLoader,
)

RULES = """\
version: "1.0"
variables:
  env: dev
defaults:
  naming_convention: snake_case
sources:
  - path: ./model.yaml
    layout: monolith
generators:
  - id: demo
    output_dir: ./out
"""


def test_load_rules(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES, encoding="utf-8")
    rules = ProjectConfigLoader().load(path)
    assert rules.version == "1.0"
    assert rules.variables["env"] == "dev"
    assert rules.generators[0].id == "demo"
    assert rules.generators[0].output_dir == Path("out")


def test_absolute_output_dir_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES.replace("./out", "/tmp/out"), encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        ProjectConfigLoader().load(path)


def test_unknown_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES.replace('"1.0"', '"2.0"'), encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        ProjectConfigLoader().load(path)


def test_discover(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES, encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert ProjectConfigLoader.discover(nested) == path


def test_source_layout_rules() -> None:
    from pydantic import ValidationError

    from eggpipe import SourceConfig

    with pytest.raises(ValidationError):
        SourceConfig.model_validate({"path": "model.yaml"})
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(
            {"path": "model.yaml", "layout": "monolith", "files": ["*.yaml"]}
        )
    with pytest.raises(ValidationError):
        SourceConfig.model_validate({"path": "models", "layout": "file-per-model"})
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(
            {"path": "models", "layout": "directory-per-model", "files": ["*.yaml"]}
        )
    config = SourceConfig(
        path=Path("models"),
        layout="directory-per-model",
        model_dirs=("*",),
        files=("*.yaml",),
    )
    assert config.model_dirs == ("*",)
