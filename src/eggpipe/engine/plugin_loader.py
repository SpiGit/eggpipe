"""Загрузка генераторов и форматов из entry points и локальных файлов."""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Any

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
        plugin, issue = _generator_from_entry(entry_point)
        if issue is not None:
            issues.append(issue)
            continue
        assert plugin is not None
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
        plugin, issue = _format_from_entry(entry_point)
        if issue is not None:
            issues.append(issue)
            continue
        assert plugin is not None
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
        module, issue = _load_local_module(path, f"_eggpipe_local_{index}", entry_name)
        if issue is not None:
            issues.append(issue)
            continue
        assert module is not None
        for value in _generator_classes(module):
            plugin, plugin_issue = _local_generator(value, entry_name)
            if plugin_issue is not None:
                issues.append(plugin_issue)
                continue
            assert plugin is not None
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


def _generator_from_entry(
    entry_point: EntryPoint,
) -> tuple[GeneratorPlugin | None, PluginIssue | None]:
    loaded, issue = _instantiate_entry(entry_point)
    if issue is not None:
        return None, issue
    if not isinstance(loaded, GeneratorPlugin):
        return None, PluginIssue(entry_point.name, "не является GeneratorPlugin")
    return _validated_generator(loaded, entry_point.name)


def _format_from_entry(entry_point: EntryPoint) -> tuple[FormatPlugin | None, PluginIssue | None]:
    loaded, issue = _instantiate_entry(entry_point)
    if issue is not None:
        return None, issue
    if not isinstance(loaded, FormatPlugin):
        return None, PluginIssue(entry_point.name, "не является FormatPlugin")
    if loaded.api_version != "1":
        return None, PluginIssue(
            entry_point.name,
            f"несовместимый api_version: {loaded.api_version}",
        )
    return loaded, None


def _instantiate_entry(entry_point: EntryPoint) -> tuple[Any | None, PluginIssue | None]:
    try:
        loaded = entry_point.load()
        return loaded() if isinstance(loaded, type) else loaded, None
    except Exception as exc:
        return None, PluginIssue(entry_point.name, f"не удалось загрузить: {exc}")


def _validated_generator(
    plugin: GeneratorPlugin,
    entry_name: str,
    *,
    check_entry_name: bool = True,
) -> tuple[GeneratorPlugin | None, PluginIssue | None]:
    try:
        validate_generator_contract(plugin)
    except PluginContractError as exc:
        return None, PluginIssue(entry_name, str(exc), exc.code)
    if plugin.api_version != "1":
        return None, PluginIssue(entry_name, f"несовместимый api_version: {plugin.api_version}")
    if check_entry_name and entry_name != plugin.id:
        return None, PluginIssue(
            entry_name,
            f"id плагина {plugin.id!r} не совпадает с entry point",
        )
    return plugin, None


def _load_local_module(
    path: Path,
    module_name: str,
    entry_name: str,
) -> tuple[Any | None, PluginIssue | None]:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None, PluginIssue(entry_name, "не удалось создать import spec")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        return None, PluginIssue(entry_name, f"не удалось импортировать: {exc}")
    return module, None


def _generator_classes(module: Any) -> list[type[Any]]:
    return [
        value
        for _, value in inspect.getmembers(module, inspect.isclass)
        if issubclass(value, GeneratorPlugin) and not inspect.isabstract(value)
    ]


def _local_generator(
    value: type[Any],
    entry_name: str,
) -> tuple[GeneratorPlugin | None, PluginIssue | None]:
    label = f"{entry_name}:{value.__name__}"
    try:
        plugin = value()
    except Exception as exc:
        return None, PluginIssue(label, f"не удалось создать плагин: {exc}")
    return _validated_generator(plugin, label, check_entry_name=False)


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
