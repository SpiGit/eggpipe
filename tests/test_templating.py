"""Tests for the optional Jinja2 helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from eggpipe.templating import TemplateError, jinja_environment, render_template


def test_package_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "demo_package"
    templates = package / "templates"
    templates.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (templates / "hello.j2").write_text("Hello {{ name }}!", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    environment = jinja_environment(package="demo_package")

    assert render_template(environment, "hello.j2", name="TPC-H") == "Hello TPC-H!"


def test_templates_dir_relative_to_config_dir(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "value.j2").write_text("{{ value }}", encoding="utf-8")

    environment = jinja_environment(templates_dir="templates", config_dir=tmp_path)

    assert render_template(environment, "value.j2", value=42) == "42"


def test_missing_templates_dir(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="template directory not found"):
        jinja_environment(templates_dir=tmp_path / "missing")


def test_missing_template(tmp_path: Path) -> None:
    environment = jinja_environment(templates_dir=tmp_path)

    with pytest.raises(TemplateError, match=r"missing\.j2"):
        render_template(environment, "missing.j2")


def test_undefined_variable_is_error(tmp_path: Path) -> None:
    (tmp_path / "strict.j2").write_text("{{ missing }}", encoding="utf-8")
    environment = jinja_environment(templates_dir=tmp_path)

    with pytest.raises(TemplateError):
        render_template(environment, "strict.j2")


def test_requires_loader_source() -> None:
    with pytest.raises(TemplateError, match="package or templates_dir"):
        jinja_environment()


def test_importing_core_does_not_import_jinja2() -> None:
    code = "import sys, eggpipe; assert 'jinja2' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
