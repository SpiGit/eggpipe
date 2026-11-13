"""Реестр форматов документов."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from eggpipe.core.model import FormatSchema
from eggpipe.interfaces.formats import EntityModelFormat, FormatPlugin
from eggpipe.utils.exceptions import (
    FormatConflictError,
    FormatInheritanceError,
    UnknownFormatError,
)

MAX_FORMAT_DEPTH = 10


@dataclass(frozen=True)
class FormatRegistryInfo:
    name: str
    versions: tuple[str, ...]
    primitive_types: frozenset[str]


class FormatRegistry:
    """Встроенный entity-model и форматы от плагинов."""

    def __init__(self, *, include_builtin: bool = True) -> None:
        self._formats: dict[str, FormatPlugin] = {}
        self._validated = False
        if include_builtin:
            self.register(EntityModelFormat())

    def register(self, plugin: FormatPlugin) -> None:
        names = getattr(plugin, "format_names", None)
        if not isinstance(names, list) or not names:
            raise FormatInheritanceError("format_names должен быть непустым списком")
        if len(set(names)) != len(names):
            raise FormatInheritanceError("format_names содержит дубликаты")
        for name in names:
            if not isinstance(name, str) or not name:
                raise FormatInheritanceError("format_names должен содержать строки")
            if name == "entity-model" and not isinstance(plugin, EntityModelFormat):
                raise FormatConflictError(
                    "entity-model зарезервирован ядром и не может быть переопределён"
                )
            if name in self._formats:
                raise FormatConflictError(f"формат уже зарегистрирован: {name}")
        for name in names:
            self._formats[name] = plugin
        self._validated = False

    def get(self, name: str) -> FormatPlugin:
        self.validate()
        try:
            return self._formats[name]
        except KeyError as exc:
            raise UnknownFormatError(f"неизвестный формат: {name}") from exc

    def list(self) -> list[FormatRegistryInfo]:
        self.validate()
        return [
            FormatRegistryInfo(
                name=name,
                versions=tuple(plugin.supported_versions),
                primitive_types=frozenset(plugin.primitive_types),
            )
            for name, plugin in sorted(self._formats.items())
        ]

    def validate(self) -> None:
        if self._validated:
            return
        plugins = {id(plugin): plugin for plugin in self._formats.values()}
        for plugin in plugins.values():
            self._validate_basic(plugin)
        for plugin in plugins.values():
            if plugin.extends is not None:
                self._validate_inheritance(plugin)
        self._validated = True

    def _validate_basic(self, plugin: FormatPlugin) -> None:
        name = _plugin_name(plugin)
        versions = _versions(plugin)
        schemas = getattr(plugin, "schemas", None)
        if not isinstance(schemas, dict):
            raise FormatInheritanceError(f"{name}: schemas должен быть словарём")
        if set(schemas) != set(versions):
            raise FormatInheritanceError(
                f"{name}: ключи schemas должны совпадать с supported_versions"
            )
        for version in versions:
            schema = schemas[version]
            if not isinstance(schema, FormatSchema):
                raise FormatInheritanceError(
                    f"{name}: schemas[{version!r}] должен быть FormatSchema"
                )
            if not _is_model(schema.layer_entity):
                raise FormatInheritanceError(
                    f"{name}: schemas[{version!r}].layer_entity должен быть BaseModel"
                )
            if not _is_model(schema.full_entity):
                raise FormatInheritanceError(
                    f"{name}: schemas[{version!r}].full_entity должен быть BaseModel"
                )

        primitives = getattr(plugin, "primitive_types", None)
        if not isinstance(primitives, (set, frozenset)) or any(
            not isinstance(item, str) for item in primitives
        ):
            raise FormatInheritanceError(f"{name}: primitive_types должен быть множеством строк")

        extends = getattr(plugin, "extends", None)
        if extends is not None and (not isinstance(extends, str) or not extends):
            raise FormatInheritanceError(f"{name}: extends должен быть непустой строкой")
        base_versions = getattr(plugin, "base_versions", None)
        if not isinstance(base_versions, dict):
            raise FormatInheritanceError(f"{name}: base_versions должен быть словарём")
        if extends is None:
            if base_versions:
                raise FormatInheritanceError(f"{name}: base_versions допустим только при extends")
            return
        if extends in plugin.format_names:
            raise FormatInheritanceError(f"{name}: формат не может наследовать сам себя")
        if set(base_versions) != set(versions):
            raise FormatInheritanceError(
                f"{name}: base_versions должен содержать запись для каждой версии"
            )
        for base_version in base_versions.values():
            if not isinstance(base_version, str) or not base_version:
                raise FormatInheritanceError(f"{name}: версии в base_versions должны быть строками")

    def _validate_inheritance(self, plugin: FormatPlugin) -> None:
        name = _plugin_name(plugin)
        parent = self._formats.get(plugin.extends or "")
        if parent is None:
            raise FormatInheritanceError(f"{name}: неизвестный базовый формат {plugin.extends!r}")

        seen: set[int] = set()
        current: FormatPlugin | None = plugin
        depth = 0
        while current is not None and current.extends is not None:
            if id(current) in seen:
                raise FormatInheritanceError(f"{name}: цикл наследования форматов")
            seen.add(id(current))
            current = self._formats.get(current.extends)
            if current is None:
                raise FormatInheritanceError(
                    f"{name}: неизвестный базовый формат {plugin.extends!r}"
                )
            depth += 1
            if depth > MAX_FORMAT_DEPTH:
                raise FormatInheritanceError(
                    f"{name}: глубина наследования больше {MAX_FORMAT_DEPTH}"
                )

        parent_versions = set(parent.supported_versions)
        for version in plugin.supported_versions:
            base_version = plugin.base_versions[version]
            if base_version not in parent_versions:
                raise FormatInheritanceError(
                    f"{name} {version}: базовая версия {base_version} не поддерживается "
                    f"{plugin.extends}"
                )
            own_schema = plugin.schemas[version]
            parent_schema = parent.schemas[base_version]
            if not issubclass(own_schema.full_entity, parent_schema.full_entity):
                raise FormatInheritanceError(
                    f"{name} {version}: full_entity должен наследовать "
                    f"full_entity {plugin.extends} {base_version}"
                )
        missing = set(parent.primitive_types) - set(plugin.primitive_types)
        if missing:
            raise FormatInheritanceError(
                f"{name}: primitive_types должен включать примитивы {plugin.extends}: "
                f"{', '.join(sorted(missing))}"
            )


def _plugin_name(plugin: FormatPlugin) -> str:
    return plugin.format_names[0] if plugin.format_names else "<unnamed>"


def _versions(plugin: FormatPlugin) -> tuple[str, ...]:
    versions = getattr(plugin, "supported_versions", None)
    if not isinstance(versions, list) or not versions:
        raise FormatInheritanceError(
            f"{_plugin_name(plugin)}: supported_versions должен быть непустым списком"
        )
    if any(not isinstance(version, str) or not version for version in versions):
        raise FormatInheritanceError(
            f"{_plugin_name(plugin)}: supported_versions должен содержать строки"
        )
    if len(set(versions)) != len(versions):
        raise FormatInheritanceError(
            f"{_plugin_name(plugin)}: supported_versions содержит дубликаты"
        )
    return tuple(versions)


def _is_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


__all__ = ["FormatRegistry", "FormatRegistryInfo"]
