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


@dataclass(frozen=True)
class _FormatContract:
    plugin: FormatPlugin
    names: tuple[str, ...]
    versions: tuple[str, ...]
    schemas: dict[str, FormatSchema]
    primitives: frozenset[str]
    extends: str | None
    base_versions: dict[str, str]

    @property
    def name(self) -> str:
        return self.names[0]


class FormatRegistry:
    """Встроенный entity-model и форматы от плагинов."""

    def __init__(self, *, include_builtin: bool = True) -> None:
        self._formats: dict[str, _FormatContract] = {}
        self._validated = False
        if include_builtin:
            self.register(EntityModelFormat())

    def register(self, plugin: FormatPlugin) -> None:
        contract = _contract(plugin)
        for name in contract.names:
            if name == "entity-model" and not isinstance(plugin, EntityModelFormat):
                raise FormatConflictError(
                    "entity-model зарезервирован ядром и не может быть переопределён"
                )
            if name in self._formats:
                raise FormatConflictError(f"формат уже зарегистрирован: {name}")
        for name in contract.names:
            self._formats[name] = contract
        self._validated = False

    def get(self, name: str) -> FormatPlugin:
        self.validate()
        try:
            return self._formats[name].plugin
        except KeyError as exc:
            raise UnknownFormatError(f"неизвестный формат: {name}") from exc

    def accepts(self, format_name: str, accepted: set[str] | None) -> bool:
        """Проверить формат с учётом цепочки extends."""
        if accepted is None:
            return True
        self.validate()
        current: str | None = format_name
        seen: set[str] = set()
        while current is not None and current not in seen:
            if current in accepted:
                return True
            seen.add(current)
            contract = self._formats.get(current)
            if contract is None:
                return False
            current = contract.extends
        return False

    def list(self) -> list[FormatRegistryInfo]:
        self.validate()
        return [
            FormatRegistryInfo(
                name=name,
                versions=contract.versions,
                primitive_types=contract.primitives,
            )
            for name, contract in sorted(self._formats.items())
        ]

    def validate(self) -> None:
        if self._validated:
            return
        contracts = {id(contract.plugin): contract for contract in self._formats.values()}
        for contract in contracts.values():
            if contract.extends is not None:
                self._validate_inheritance(contract)
        self._validated = True

    def _validate_inheritance(self, contract: _FormatContract) -> None:
        parent = self._formats.get(contract.extends or "")
        if parent is None:
            raise FormatInheritanceError(
                f"{contract.name}: неизвестный базовый формат {contract.extends!r}"
            )

        seen: set[int] = set()
        current: _FormatContract | None = contract
        depth = 0
        while current is not None and current.extends is not None:
            if id(current) in seen:
                raise FormatInheritanceError(f"{contract.name}: цикл наследования форматов")
            seen.add(id(current))
            current = self._formats.get(current.extends)
            if current is None:
                raise FormatInheritanceError(
                    f"{contract.name}: неизвестный базовый формат {contract.extends!r}"
                )
            depth += 1
            if depth > MAX_FORMAT_DEPTH:
                raise FormatInheritanceError(
                    f"{contract.name}: глубина наследования больше {MAX_FORMAT_DEPTH}"
                )

        for version in contract.versions:
            base_version = contract.base_versions[version]
            if base_version not in parent.versions:
                raise FormatInheritanceError(
                    f"{contract.name} {version}: базовая версия {base_version} не "
                    f"поддерживается {contract.extends}"
                )
            own_schema = contract.schemas[version]
            parent_schema = parent.schemas[base_version]
            if not issubclass(own_schema.full_entity, parent_schema.full_entity):
                raise FormatInheritanceError(
                    f"{contract.name} {version}: full_entity должен наследовать "
                    f"full_entity {contract.extends} {base_version}"
                )
        missing = set(parent.primitives) - set(contract.primitives)
        if missing:
            raise FormatInheritanceError(
                f"{contract.name}: primitive_types должен включать примитивы "
                f"{contract.extends}: {', '.join(sorted(missing))}"
            )


def _contract(plugin: FormatPlugin) -> _FormatContract:
    names = getattr(plugin, "format_names", None)
    if not isinstance(names, list) or not names:
        raise FormatInheritanceError("format_names должен быть непустым списком")
    if len(set(names)) != len(names):
        raise FormatInheritanceError("format_names содержит дубликаты")
    if any(not isinstance(name, str) or not name for name in names):
        raise FormatInheritanceError("format_names должен содержать строки")

    versions = getattr(plugin, "supported_versions", None)
    if not isinstance(versions, list) or not versions:
        raise FormatInheritanceError(f"{names[0]}: supported_versions должен быть непустым списком")
    if any(not isinstance(version, str) or not version for version in versions):
        raise FormatInheritanceError(f"{names[0]}: supported_versions должен содержать строки")
    if len(set(versions)) != len(versions):
        raise FormatInheritanceError(f"{names[0]}: supported_versions содержит дубликаты")

    schemas = getattr(plugin, "schemas", None)
    if not isinstance(schemas, dict):
        raise FormatInheritanceError(f"{names[0]}: schemas должен быть словарём")
    if set(schemas) != set(versions):
        raise FormatInheritanceError(
            f"{names[0]}: ключи schemas должны совпадать с supported_versions"
        )
    for version in versions:
        schema = schemas[version]
        if not isinstance(schema, FormatSchema):
            raise FormatInheritanceError(
                f"{names[0]}: schemas[{version!r}] должен быть FormatSchema"
            )
        if not _is_model(schema.layer_entity):
            raise FormatInheritanceError(
                f"{names[0]}: schemas[{version!r}].layer_entity должен быть BaseModel"
            )
        if not _is_model(schema.full_entity):
            raise FormatInheritanceError(
                f"{names[0]}: schemas[{version!r}].full_entity должен быть BaseModel"
            )

    primitives = getattr(plugin, "primitive_types", None)
    if not isinstance(primitives, (set, frozenset)) or any(
        not isinstance(item, str) for item in primitives
    ):
        raise FormatInheritanceError(f"{names[0]}: primitive_types должен быть множеством строк")

    extends = getattr(plugin, "extends", None)
    if extends is not None and (not isinstance(extends, str) or not extends):
        raise FormatInheritanceError(f"{names[0]}: extends должен быть непустой строкой")
    base_versions = getattr(plugin, "base_versions", None)
    if not isinstance(base_versions, dict):
        raise FormatInheritanceError(f"{names[0]}: base_versions должен быть словарём")
    if extends is None:
        if base_versions:
            raise FormatInheritanceError(f"{names[0]}: base_versions допустим только при extends")
    else:
        if extends in names:
            raise FormatInheritanceError(f"{names[0]}: формат не может наследовать сам себя")
        if set(base_versions) != set(versions):
            raise FormatInheritanceError(
                f"{names[0]}: base_versions должен содержать запись для каждой версии"
            )
        if any(not isinstance(value, str) or not value for value in base_versions.values()):
            raise FormatInheritanceError(f"{names[0]}: версии в base_versions должны быть строками")

    return _FormatContract(
        plugin=plugin,
        names=tuple(names),
        versions=tuple(versions),
        schemas=dict(schemas),
        primitives=frozenset(primitives),
        extends=extends,
        base_versions=dict(base_versions),
    )


def _is_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


__all__ = ["FormatRegistry", "FormatRegistryInfo"]
