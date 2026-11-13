"""Document format registry."""

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
    """Built-in entity-model plus formats from plugins."""

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
                    "entity-model is reserved by the core and cannot be overridden"
                )
            if name in self._formats:
                raise FormatConflictError(f"format is already registered: {name}")
        for name in contract.names:
            self._formats[name] = contract
        self._validated = False

    def get(self, name: str) -> FormatPlugin:
        self.validate()
        try:
            return self._formats[name].plugin
        except KeyError as exc:
            raise UnknownFormatError(f"unknown format: {name}") from exc

    def accepts(self, format_name: str, accepted: set[str] | None) -> bool:
        """Check a format, following the extends chain."""
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
                f"{contract.name}: unknown base format {contract.extends!r}"
            )

        seen: set[int] = set()
        current: _FormatContract | None = contract
        depth = 0
        while current is not None and current.extends is not None:
            if id(current) in seen:
                raise FormatInheritanceError(f"{contract.name}: format inheritance cycle")
            seen.add(id(current))
            current = self._formats.get(current.extends)
            if current is None:
                raise FormatInheritanceError(
                    f"{contract.name}: unknown base format {contract.extends!r}"
                )
            depth += 1
            if depth > MAX_FORMAT_DEPTH:
                raise FormatInheritanceError(
                    f"{contract.name}: inheritance depth exceeds {MAX_FORMAT_DEPTH}"
                )

        for version in contract.versions:
            base_version = contract.base_versions[version]
            if base_version not in parent.versions:
                raise FormatInheritanceError(
                    f"{contract.name} {version}: base version {base_version} is not "
                    f"supported by {contract.extends}"
                )
            own_schema = contract.schemas[version]
            parent_schema = parent.schemas[base_version]
            if not issubclass(own_schema.full_entity, parent_schema.full_entity):
                raise FormatInheritanceError(
                    f"{contract.name} {version}: full_entity must inherit "
                    f"full_entity {contract.extends} {base_version}"
                )
        missing = set(parent.primitives) - set(contract.primitives)
        if missing:
            raise FormatInheritanceError(
                f"{contract.name}: primitive_types must include the primitives of "
                f"{contract.extends}: {', '.join(sorted(missing))}"
            )


def _contract(plugin: FormatPlugin) -> _FormatContract:
    names = getattr(plugin, "format_names", None)
    if not isinstance(names, list) or not names:
        raise FormatInheritanceError("format_names must be a non-empty list")
    if len(set(names)) != len(names):
        raise FormatInheritanceError("format_names contains duplicates")
    if any(not isinstance(name, str) or not name for name in names):
        raise FormatInheritanceError("format_names must contain strings")

    versions = getattr(plugin, "supported_versions", None)
    if not isinstance(versions, list) or not versions:
        raise FormatInheritanceError(f"{names[0]}: supported_versions must be a non-empty list")
    if any(not isinstance(version, str) or not version for version in versions):
        raise FormatInheritanceError(f"{names[0]}: supported_versions must contain strings")
    if len(set(versions)) != len(versions):
        raise FormatInheritanceError(f"{names[0]}: supported_versions contains duplicates")

    schemas = getattr(plugin, "schemas", None)
    if not isinstance(schemas, dict):
        raise FormatInheritanceError(f"{names[0]}: schemas must be a mapping")
    if set(schemas) != set(versions):
        raise FormatInheritanceError(f"{names[0]}: schemas keys must match supported_versions")
    for version in versions:
        schema = schemas[version]
        if not isinstance(schema, FormatSchema):
            raise FormatInheritanceError(f"{names[0]}: schemas[{version!r}] must be a FormatSchema")
        if not _is_model(schema.layer_entity):
            raise FormatInheritanceError(
                f"{names[0]}: schemas[{version!r}].layer_entity must be a BaseModel"
            )
        if not _is_model(schema.full_entity):
            raise FormatInheritanceError(
                f"{names[0]}: schemas[{version!r}].full_entity must be a BaseModel"
            )

    primitives = getattr(plugin, "primitive_types", None)
    if not isinstance(primitives, (set, frozenset)) or any(
        not isinstance(item, str) for item in primitives
    ):
        raise FormatInheritanceError(f"{names[0]}: primitive_types must be a set of strings")

    extends = getattr(plugin, "extends", None)
    if extends is not None and (not isinstance(extends, str) or not extends):
        raise FormatInheritanceError(f"{names[0]}: extends must be a non-empty string")
    base_versions = getattr(plugin, "base_versions", None)
    if not isinstance(base_versions, dict):
        raise FormatInheritanceError(f"{names[0]}: base_versions must be a mapping")
    if extends is None:
        if base_versions:
            raise FormatInheritanceError(f"{names[0]}: base_versions is only allowed with extends")
    else:
        if extends in names:
            raise FormatInheritanceError(f"{names[0]}: a format cannot extend itself")
        if set(base_versions) != set(versions):
            raise FormatInheritanceError(
                f"{names[0]}: base_versions must contain an entry for every version"
            )
        if any(not isinstance(value, str) or not value for value in base_versions.values()):
            raise FormatInheritanceError(f"{names[0]}: versions in base_versions must be strings")

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
