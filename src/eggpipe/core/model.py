"""Internal immutable core models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

PRIMITIVE_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "text",
        "integer",
        "bigint",
        "boolean",
        "float",
        "date",
        "datetime",
        "uuid",
        "json",
    }
)


class _Unset:
    """Sentinel for "value not set"."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()

DefaultValue = str | int | float | bool | date | datetime | None


@dataclass(frozen=True)
class FormatInfo:
    """Concrete format and version."""

    name: str
    version: str


class MergePolicy(StrEnum):
    """Merge policy for layer collections."""

    KEYED = "keyed"
    APPEND = "append"
    UNION = "union"
    ERROR = "error"


@dataclass(frozen=True)
class FormatSchema:
    """Pydantic schemas for one layer and the final entity."""

    layer_entity: type[BaseModel]
    full_entity: type[BaseModel]


class EntityIdentity(BaseModel):
    """Minimal entity identity model for a delta layer."""

    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")

    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldIdentity(BaseModel):
    """Minimal field identity model for a delta layer."""

    name: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    model_config = ConfigDict(extra="forbid", frozen=True)


class Constraints(BaseModel):
    min: int | float | date | datetime | None = None
    max: int | float | date | datetime | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldDef(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: str
    description: str | None = None
    required: bool = False
    nullable: bool = False
    default: DefaultValue | _Unset = UNSET
    constraints: Constraints | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: Path | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer("default")
    def _serialize_default(self, value: object, _info: object) -> object:
        # UNSET is not serialized to JSON as a value; model_serializer removes the key.
        return None if value is UNSET else value

    @model_validator(mode="after")
    def _coerce_temporal_default(self) -> FieldDef:
        if self.type == "date" and isinstance(self.default, str):
            try:
                return self.model_copy(update={"default": date.fromisoformat(self.default)})
            except ValueError:
                return self
        if self.type == "datetime" and isinstance(self.default, str):
            try:
                return self.model_copy(
                    update={"default": datetime.fromisoformat(self.default.replace("Z", "+00:00"))}
                )
            except ValueError:
                return self
        return self

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        data = handler(self)
        if self.default is UNSET:
            data.pop("default", None)
        return data


class ExtendsRef(BaseModel):
    import_: str = Field(alias="import")
    entity: str

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class LayerEntity(EntityIdentity):
    """Partial entity schema for a layer file."""

    description: str | None = None
    version: str | int | None = None
    updated_at: date | datetime | None = None
    extends: str | ExtendsRef | None = None
    fields: tuple[FieldDef, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    version: str | int | None = None
    updated_at: date | datetime | None = None
    extends: str | ExtendsRef | None = None
    fields: tuple[FieldDef, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: Path | None = Field(default=None, exclude=True, repr=False)
    format: str | None = Field(default=None, exclude=True, repr=False)
    format_version: str | None = Field(default=None, exclude=True, repr=False)
    layer_sources: tuple[Path, ...] = Field(default=(), exclude=True, repr=False)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("updated_at", mode="before")
    @classmethod
    def _coerce_updated_at(cls, value: object) -> object:
        # Pydantic smart union parses midnight ISO-datetime as date; preserve the type.
        if isinstance(value, str) and ("T" in value or " " in value):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value


class EnumValue(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str | int | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class EnumDef(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    values: tuple[EnumValue, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CustomType(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    base: str
    constraints: Constraints | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class _IndexedModel(BaseModel):
    """Immutable model with name indexes."""

    entities: tuple[Entity, ...] = ()
    enums: tuple[EnumDef, ...] = ()
    types: tuple[CustomType, ...] = ()

    _entity_map: dict[str, Entity] = PrivateAttr(default_factory=dict)
    _enum_map: dict[str, EnumDef] = PrivateAttr(default_factory=dict)
    _type_map: dict[str, CustomType] = PrivateAttr(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _build_maps(self) -> _IndexedModel:
        object.__setattr__(self, "_entity_map", {item.name: item for item in self.entities})
        object.__setattr__(self, "_enum_map", {item.name: item for item in self.enums})
        object.__setattr__(self, "_type_map", {item.name: item for item in self.types})
        return self

    def entity(self, name: str) -> Entity:
        return self._entity_map[name]

    def enum(self, name: str) -> EnumDef:
        return self._enum_map[name]

    def type(self, name: str) -> CustomType:
        return self._type_map[name]

    def resolve_type(self, field: FieldDef) -> Entity | EnumDef | CustomType | str:
        if field.type in self._entity_map:
            return self._entity_map[field.type]
        if field.type in self._enum_map:
            return self._enum_map[field.type]
        if field.type in self._type_map:
            return self._type_map[field.type]
        return field.type


class ModelSlice(_IndexedModel):
    @property
    def formats(self) -> frozenset[FormatInfo]:
        return frozenset(
            FormatInfo(entity.format, entity.format_version)
            for entity in self.entities
            if entity.format is not None and entity.format_version is not None
        )


class SourceModel(ModelSlice):
    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputSelection(BaseModel):
    """Model subset selection; None/empty means all."""

    entities: tuple[str, ...] | None = None
    enums: tuple[str, ...] | None = None
    types: tuple[str, ...] | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = [
    "PRIMITIVE_TYPES",
    "UNSET",
    "CustomType",
    "DefaultValue",
    "Entity",
    "EntityIdentity",
    "EnumDef",
    "EnumValue",
    "ExtendsRef",
    "FieldDef",
    "FieldIdentity",
    "FormatInfo",
    "FormatSchema",
    "InputSelection",
    "LayerEntity",
    "MergePolicy",
    "ModelSlice",
    "SourceModel",
]
