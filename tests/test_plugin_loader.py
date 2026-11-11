"""Тесты загрузчика генераторов."""

from __future__ import annotations

import pytest

from metadata_generator import GenerationResult, GeneratorInput, GeneratorPlugin
from metadata_generator.engine import plugin_loader


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
    def __init__(self, name: str, value: type[GeneratorPlugin]) -> None:
        self.name = name
        self.value = value

    def load(self) -> type[GeneratorPlugin]:
        return self.value


def test_load_generators(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [EntryPoint("demo", DemoGenerator), EntryPoint("broken", BrokenGenerator)]

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        return entries

    monkeypatch.setattr(plugin_loader, "entry_points", fake_entry_points)
    assert set(plugin_loader.load_generators()) == {"demo"}
