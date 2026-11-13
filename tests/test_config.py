"""Тесты .eggpipe.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from eggpipe import (
    ConfigValidationError,
    GeneratorRulesLoader,
)

RULES = """\
version: "1.0"
variables:
  env: dev
defaults:
  naming_convention: snake_case
sources:
  - path: ./model.yaml
generators:
  - id: demo
    output_dir: ./out
"""


def test_load_rules(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES, encoding="utf-8")
    rules = GeneratorRulesLoader().load(path)
    assert rules.version == "1.0"
    assert rules.variables["env"] == "dev"
    assert rules.generators[0].id == "demo"
    assert rules.generators[0].output_dir == Path("out")


def test_absolute_output_dir_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES.replace("./out", "/tmp/out"), encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        GeneratorRulesLoader().load(path)


def test_unknown_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES.replace('"1.0"', '"2.0"'), encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        GeneratorRulesLoader().load(path)


def test_discover(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe.yaml"
    path.write_text(RULES, encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert GeneratorRulesLoader.discover(nested) == path
