"""Загрузка генераторов и форматов из entry points и локальных файлов."""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

from metadata_generator.engine.format_registry import FormatRegistry
from metadata_generator.interfaces.formats import FormatPlugin
from metadata_generator.interfaces.generator import GeneratorPlugin

GENERATOR_GROUP = "metadata_generator.generators"
FORMAT_GROUP = "metadata_generator.formats"


@dataclass(frozen=True)
class PluginIssue:
    entry_point: str
    message: str


def load_generators_with_issues() -> tuple[dict[str, GeneratorPlugin], list[PluginIssue]]:
    result: dict[str, GeneratorPlugin] = {}
    issues: list[PluginIssue] = []
    entries = sorted(entry_points(group=GENERATOR_GROUP), key=lambda item: item.name)
    for entry_point in entries:
        try:
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
        except Exception as exc:
            issues.append(PluginIssue(entry_point.name, f"не удалось загрузить: {exc}"))
            continue
        if not isinstance(plugin, GeneratorPlugin):
            issues.append(PluginIssue(entry_point.name, "не является GeneratorPlugin"))
            continue
        if plugin.api_version != "1":
            issues.append(
                PluginIssue(
                    entry_point.name,
                    f"несовместимый api_version: {plugin.api_version}",
                )
            )
            continue
        if entry_point.name != plugin.id:
            issues.append(
                PluginIssue(
                    entry_point.name,
                    f"id плагина {plugin.id!r} не совпадает с entry point",
                )
            )
            continue
        if plugin.id in result:
            issues.append(PluginIssue(entry_point.name, f"дубликат id генератора: {plugin.id}"))
            continue
        result[plugin.id] = plugin
    return result, issues


def load_generators() -> dict[str, GeneratorPlugin]:
    return load_generators_with_issues()[0]


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
    "PluginIssue",
    "build_format_registry",
    "load_formats",
    "load_generators",
    "load_generators_with_issues",
    "load_local_generators",
]
