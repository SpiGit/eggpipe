"""Загрузка генераторов и форматов из entry points и локальных файлов."""

from __future__ import annotations

import importlib.util
import inspect
from importlib.metadata import entry_points
from pathlib import Path

from metadata_generator.engine.format_registry import FormatRegistry
from metadata_generator.interfaces.formats import FormatPlugin
from metadata_generator.interfaces.generator import GeneratorPlugin

GENERATOR_GROUP = "metadata_generator.generators"
FORMAT_GROUP = "metadata_generator.formats"


def load_generators() -> dict[str, GeneratorPlugin]:
    result: dict[str, GeneratorPlugin] = {}
    for entry_point in entry_points(group=GENERATOR_GROUP):
        try:
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
        except Exception:
            continue
        if not isinstance(plugin, GeneratorPlugin):
            continue
        if plugin.api_version != "1":
            continue
        config_id = plugin.id
        if entry_point.name != config_id:
            continue
        result[config_id] = plugin
    return result


def load_formats() -> list[FormatPlugin]:
    result: list[FormatPlugin] = []
    for entry_point in entry_points(group=FORMAT_GROUP):
        try:
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
        except Exception:
            continue
        if not isinstance(plugin, FormatPlugin):
            continue
        if plugin.api_version != "1":
            continue
        result.append(plugin)
    return result


def build_format_registry() -> FormatRegistry:
    registry = FormatRegistry()
    for plugin in load_formats():
        registry.register(plugin)
    return registry


def load_local_generators(paths: list[Path]) -> dict[str, GeneratorPlugin]:
    result: dict[str, GeneratorPlugin] = {}
    for index, path in enumerate(paths):
        module_name = f"_metadata_generator_local_{index}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        for _, value in inspect.getmembers(module, inspect.isclass):
            if not issubclass(value, GeneratorPlugin) or inspect.isabstract(value):
                continue
            try:
                plugin = value()
            except Exception:
                continue
            if plugin.api_version == "1":
                result.setdefault(plugin.id, plugin)
    return result


__all__ = [
    "FORMAT_GROUP",
    "GENERATOR_GROUP",
    "build_format_registry",
    "load_formats",
    "load_generators",
    "load_local_generators",
]
