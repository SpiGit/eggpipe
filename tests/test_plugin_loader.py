"""Tests for the generator loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from eggpipe import (
    Artifact,
    Entity,
    FormatSchema,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    ModelDocument,
    ModelSlice,
    SourceModel,
    generator,
)
from eggpipe.engine import plugin_loader
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import PluginContractError


@generator(input_formats={"entity-model"})
def Decorated(model: ModelSlice) -> list[Artifact]:
    return []


@generator(id="bad-signature", input_formats={"entity-model"})
def BadSignature(model: ModelSlice, extra: str) -> Artifact:
    return Artifact(path="a.txt", content=extra)


class DemoGenerator(GeneratorPlugin):
    id = "demo"
    name = "Demo"
    input_formats: ClassVar[set[str] | None] = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class MissingGenerator(GeneratorPlugin):
    id = "missing"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class BrokenGenerator(GeneratorPlugin):
    api_version = "2"  # type: ignore[assignment]
    id = "broken"
    input_formats: ClassVar[set[str] | None] = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


class RaisingEntryPoint:
    name = "bad-plugin"
    value = "bad_plugin:thing"

    def load(self) -> None:
        raise PluginContractError("EG301", "input_formats must be set[str] or None")


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


def test_decorator_generator_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return [EntryPoint("decorated", Decorated)]

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    plugins, issues = plugin_loader.load_generators_with_issues()
    assert issues == []
    assert set(plugins) == {"decorated"}


def test_missing_input_formats_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [EntryPoint("missing", MissingGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    plugins, issues = plugin_loader.load_generators_with_issues()
    assert plugins == {}
    issue = issues[0]
    assert issue.entry_point == "missing"
    assert issue.code == "EG301"
    assert "input_formats is not declared" in issue.message
    assert "test_plugin_loader" in issue.message
    assert "Missing" in issue.message
    assert "EG30" not in issue.message
    assert not issue.message.startswith("missing:")


def test_contract_issue_prints_code_once_in_cli_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [EntryPoint("missing", MissingGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    _, issues = plugin_loader.load_generators_with_issues()
    issue = issues[0]
    line = f"warning: {issue.entry_point}: {issue.code}: {issue.message}"
    assert line.count("EG301") == 1
    assert line.count("warning: missing:") == 1


def test_eg302_issue_keeps_other_plugins_and_names_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [
        EntryPoint("bad-signature", BadSignature),
        EntryPoint("demo", DemoGenerator),
    ]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    plugins, issues = plugin_loader.load_generators_with_issues()
    assert set(plugins) == {"demo"}
    assert len(issues) == 1
    issue = issues[0]
    assert issue.entry_point == "bad-signature"
    assert issue.code == "EG302"
    assert "'extra'" in issue.message
    assert "test_plugin_loader" in issue.message
    assert "BadSignature" in issue.message
    assert "ModelSlice, GenerationContext or GeneratorConfig" in issue.message
    assert "eggpipe.interfaces" not in issue.message
    assert "EG30" not in issue.message


def test_loader_level_issues_have_no_contract_code(monkeypatch: pytest.MonkeyPatch) -> None:
    class Duplicate(GeneratorPlugin):
        id = "demo"
        input_formats: ClassVar[set[str] | None] = None

        def generate(self, input: GeneratorInput) -> GenerationResult:
            return GenerationResult()

    entries = [
        EntryPoint("demo", DemoGenerator),
        EntryPoint("demo", Duplicate),
        EntryPoint("wrong-name", DemoGenerator),
        EntryPoint("broken", BrokenGenerator),
    ]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    _, issues = plugin_loader.load_generators_with_issues()
    assert all(issue.code is None for issue in issues)
    messages = " ".join(issue.message for issue in issues)
    assert "duplicate generator id 'demo'" in messages
    assert "does not match the entry point 'wrong-name'" in messages
    assert "incompatible api_version '2'" in messages


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
from typing import ClassVar

from eggpipe import GenerationResult, GeneratorInput, GeneratorPlugin

class Local(GeneratorPlugin):
    id = "local"
    name = "Local"
    input_formats: ClassVar[set[str] | None] = None

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
    assert "failed to import" in issues[0].message


def test_decoration_error_keeps_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_entry_points(*, group: str) -> list[RaisingEntryPoint]:
        return [RaisingEntryPoint()] if group == plugin_loader.GENERATOR_GROUP else []

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    plugins, issues = plugin_loader.load_generators_with_issues()
    assert plugins == {}
    assert len(issues) == 1
    issue = issues[0]
    assert issue.entry_point == "bad-plugin"
    assert issue.code == "EG301"
    assert "EG30" not in issue.message
    assert "input_formats must be set[str] or None" in issue.message
    assert "@generator" in issue.message
