"""Load generators and formats from entry points and local files."""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Any

from eggpipe.core.format_registry import FormatRegistry
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


def _module_name(value: Any) -> str | None:
    module = getattr(value, "__module__", None)
    return module if isinstance(module, str) and module else None


def _entry_module(entry_point: EntryPoint) -> str | None:
    module = getattr(entry_point, "module", None)
    if isinstance(module, str) and module:
        return module
    value = getattr(entry_point, "value", None)
    if isinstance(value, str) and value:
        return value.partition(":")[0] or None
    return None


def _issue(
    entry_name: str,
    message: str,
    *,
    code: str | None = None,
    module: str | None = None,
) -> PluginIssue:
    location = f"{entry_name} ({module})" if module else entry_name
    return PluginIssue(entry_name, f"{location}: {message}", code)


def _entry_issue(
    entry_point: EntryPoint,
    message: str,
    *,
    code: str | None = None,
    module: str | None = None,
) -> PluginIssue:
    return _issue(
        entry_point.name,
        message,
        code=code,
        module=module or _entry_module(entry_point),
    )


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
            issues.append(
                _entry_issue(
                    entry_point,
                    f"duplicate generator id {plugin.id!r}; keep a single entry point for this id",
                    code="EG301",
                    module=_module_name(type(plugin)),
                )
            )
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
                    _issue(
                        f"{entry_name}:{value.__name__}",
                        f"duplicate generator id {plugin.id!r}; keep a single class for this id",
                        code="EG301",
                        module=_module_name(value),
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
        return None, _entry_issue(
            entry_point,
            "object is not a GeneratorPlugin; the entry point must point to a "
            "GeneratorPlugin subclass or a @generator-decorated function",
            code="EG301",
            module=_module_name(type(loaded)),
        )
    return _validated_generator(loaded, entry_point.name)


def _format_from_entry(entry_point: EntryPoint) -> tuple[FormatPlugin | None, PluginIssue | None]:
    loaded, issue = _instantiate_entry(entry_point)
    if issue is not None:
        return None, issue
    if not isinstance(loaded, FormatPlugin):
        return None, _entry_issue(
            entry_point,
            "object is not a FormatPlugin; the entry point must point to a FormatPlugin subclass",
            module=_module_name(type(loaded)),
        )
    if loaded.api_version != "1":
        return None, _entry_issue(
            entry_point,
            f"incompatible api_version {loaded.api_version!r}; contract version 1 "
            'is required (api_version = "1")',
            module=_module_name(type(loaded)),
        )
    return loaded, None


def _instantiate_entry(entry_point: EntryPoint) -> tuple[Any | None, PluginIssue | None]:
    try:
        loaded = entry_point.load()
        instance = loaded() if isinstance(loaded, type) else loaded
        return instance, None
    except Exception as exc:
        return None, _entry_issue(
            entry_point,
            f"failed to load ({exc}); check that the module is installed and the "
            "entry point attribute path is correct",
        )


def _validated_generator(
    plugin: GeneratorPlugin,
    entry_name: str,
    *,
    check_entry_name: bool = True,
) -> tuple[GeneratorPlugin | None, PluginIssue | None]:
    module = _module_name(type(plugin))
    try:
        validate_generator_contract(plugin)
    except PluginContractError as exc:
        return None, _issue(entry_name, str(exc), code=exc.code, module=module)
    if plugin.api_version != "1":
        return None, _issue(
            entry_name,
            f"incompatible api_version {plugin.api_version!r}; contract version 1 "
            'is required (api_version = "1")',
            code="EG301",
            module=module,
        )
    if check_entry_name and entry_name != plugin.id:
        return None, _issue(
            entry_name,
            f"plugin id {plugin.id!r} does not match the entry point {entry_name!r}; "
            "the entry point name must equal the generator id",
            code="EG301",
            module=module,
        )
    return plugin, None


def _load_local_module(
    path: Path,
    module_name: str,
    entry_name: str,
) -> tuple[Any | None, PluginIssue | None]:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None, _issue(
            entry_name,
            "failed to create an import spec; check the file path and Python syntax",
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        return None, _issue(
            entry_name,
            f"failed to import ({exc}); fix the import error before loading the plugin",
        )
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
        return None, _issue(
            label,
            f"failed to create plugin ({exc}); the class must be instantiable without arguments",
            module=_module_name(value),
        )
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
