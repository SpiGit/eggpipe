"""Загрузка генераторов и форматов из entry points и локальных файлов."""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

from eggpipe.engine.format_registry import FormatRegistry
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.interfaces.generator import GeneratorPlugin, validate_generator_contract
from eggpipe.utils.exceptions import PluginContractError

GENERATOR_GROUP = "eggpipe.generators"
FORMAT_GROUP = "eggpipe.formats"


@dataclass(frozen=True)
class PluginIssue:
    entry_point: str
    message: str
    code: str | None = None


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
        try:
            validate_generator_contract(plugin)
        except PluginContractError as exc:
            issues.append(PluginIssue(entry_point.name, str(exc), exc.code))
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


def load_formats_with_issues() -> tuple[list[FormatPlugin], list[PluginIssue]]:
    result: list[FormatPlugin] = []
    issues: list[PluginIssue] = []
    entries = sorted(entry_points(group=FORMAT_GROUP), key=lambda item: item.name)
    for entry_point in entries:
        try:
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
        except Exception as exc:
            issues.append(PluginIssue(entry_point.name, f"не удалось загрузить: {exc}"))
            continue
        if not isinstance(plugin, FormatPlugin):
            issues.append(PluginIssue(entry_point.name, "не является FormatPlugin"))
            continue
        if plugin.api_version != "1":
            issues.append(
                PluginIssue(
                    entry_point.name,
                    f"несовместимый api_version: {plugin.api_version}",
                )
            )
            continue
        result.append(plugin)
    return result, issues


def load_formats() -> list[FormatPlugin]:
    return load_formats_with_issues()[0]


def build_format_registry() -> FormatRegistry:
    registry, _ = build_format_registry_with_issues()
    return registry


def build_format_registry_with_issues() -> tuple[FormatRegistry, list[PluginIssue]]:
    registry = FormatRegistry()
    plugins, issues = load_formats_with_issues()
    for plugin in plugins:
        registry.register(plugin)
    return registry, issues


def load_local_generators_with_issues(
    paths: list[Path],
) -> tuple[dict[str, GeneratorPlugin], list[PluginIssue]]:
    result: dict[str, GeneratorPlugin] = {}
    issues: list[PluginIssue] = []
    for index, path in enumerate(paths):
        entry_name = str(path)
        module_name = f"_eggpipe_local_{index}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            issues.append(PluginIssue(entry_name, "не удалось создать import spec"))
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            issues.append(PluginIssue(entry_name, f"не удалось импортировать: {exc}"))
            continue
        for _, value in inspect.getmembers(module, inspect.isclass):
            if not issubclass(value, GeneratorPlugin) or inspect.isabstract(value):
                continue
            try:
                plugin = value()
            except Exception as exc:
                issues.append(
                    PluginIssue(
                        f"{entry_name}:{value.__name__}",
                        f"не удалось создать плагин: {exc}",
                    )
                )
                continue
            try:
                validate_generator_contract(plugin)
            except PluginContractError as exc:
                issues.append(PluginIssue(f"{entry_name}:{value.__name__}", str(exc), exc.code))
                continue
            if plugin.api_version != "1":
                issues.append(
                    PluginIssue(
                        f"{entry_name}:{value.__name__}",
                        f"несовместимый api_version: {plugin.api_version}",
                    )
                )
                continue
            if plugin.id in result:
                issues.append(
                    PluginIssue(
                        f"{entry_name}:{value.__name__}",
                        f"дубликат id генератора: {plugin.id}",
                    )
                )
                continue
            result[plugin.id] = plugin
    return result, issues


def load_local_generators(paths: list[Path]) -> dict[str, GeneratorPlugin]:
    return load_local_generators_with_issues(paths)[0]


__all__ = [
    "FORMAT_GROUP",
    "GENERATOR_GROUP",
    "PluginIssue",
    "build_format_registry",
    "build_format_registry_with_issues",
    "load_formats",
    "load_formats_with_issues",
    "load_generators",
    "load_generators_with_issues",
    "load_local_generators",
    "load_local_generators_with_issues",
]
