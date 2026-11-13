"""Тесты загрузчика генераторов."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from eggpipe import (
    Entity,
    FormatSchema,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    ModelDocument,
    SourceModel,
)
from eggpipe.engine import plugin_loader
from eggpipe.interfaces.formats import FormatPlugin


class DemoGenerator(GeneratorPlugin):
    id = "demo"
    name = "Demo"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class BrokenGenerator(GeneratorPlugin):
    api_version = "2"  # type: ignore[assignment]
    id = "broken"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class EntryPoint:
    def __init__(self, name: str, value: type[GeneratorPlugin] | type[FormatPlugin]) -> None:
        self.name = name
        self.value = value

    def load(self) -> type[GeneratorPlugin] | type[FormatPlugin]:
        return self.value


class CustomFormat(FormatPlugin):
    format_names: ClassVar[list[str]] = ["custom"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    primitive_types: ClassVar[set[str]] = {"string"}
    schemas: ClassVar[dict[str, FormatSchema]] = {
        "1.0": FormatSchema(layer_entity=Entity, full_entity=Entity)
    }

    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        return ModelDocument(
            format="custom",
            version="1.0",
            path=base_path,
            model=SourceModel(),
        )


class BrokenFormat(CustomFormat):
    api_version = "2"  # type: ignore[assignment]
    format_names: ClassVar[list[str]] = ["broken-format"]


def test_load_generators(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [EntryPoint("demo", DemoGenerator), EntryPoint("broken", BrokenGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    assert set(plugin_loader.load_generators()) == {"demo"}


def test_generator_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        EntryPoint("demo", DemoGenerator),
        EntryPoint("wrong-name", DemoGenerator),
        EntryPoint("broken", BrokenGenerator),
    ]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    plugins, issues = plugin_loader.load_generators_with_issues()
    assert set(plugins) == {"demo"}
    assert {item.entry_point for item in issues} == {"wrong-name", "broken"}


def test_load_formats_and_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        if group == plugin_loader.FORMAT_GROUP:
            return [EntryPoint("custom", CustomFormat)]
        return []

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    formats = plugin_loader.load_formats()
    assert [item.format_names for item in formats] == [["custom"]]
    registry = plugin_loader.build_format_registry()
    assert registry.get("custom").format_names == ["custom"]


def test_format_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        if group == plugin_loader.FORMAT_GROUP:
            return [
                EntryPoint("custom", CustomFormat),
                EntryPoint("broken", BrokenFormat),
                EntryPoint("not-a-format", DemoGenerator),
            ]
        return []

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    formats, issues = plugin_loader.load_formats_with_issues()
    assert [item.format_names for item in formats] == [["custom"]]
    assert {item.entry_point for item in issues} == {"broken", "not-a-format"}


def test_load_local_generators(tmp_path: Path) -> None:
    module = tmp_path / "local_plugin.py"
    module.write_text(
        """\
from eggpipe import GenerationResult, GeneratorInput, GeneratorPlugin

class Local(GeneratorPlugin):
    id = "local"
    name = "Local"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()
""",
        encoding="utf-8",
    )
    assert set(plugin_loader.load_local_generators([module])) == {"local"}


def test_load_local_generators_reports_import_error(tmp_path: Path) -> None:
    module = tmp_path / "broken_plugin.py"
    module.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    plugins, issues = plugin_loader.load_local_generators_with_issues([module])
    assert plugins == {}
    assert issues[0].entry_point == str(module)
    assert "не удалось импортировать" in issues[0].message
