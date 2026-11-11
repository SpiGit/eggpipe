"""Внутренние immutable-модели ядра."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pydantic as pyd
from pydantic import ConfigDict, PrivateAttr, field_serializer, model_validator

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
    """Sentinel для «значение не задано»."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()

DefaultValue = str | int | float | bool | date | datetime | None


class Constraints(pyd.BaseModel):
    min: int | float | date | datetime | None = None
    max: int | float | date | datetime | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldDef(pyd.BaseModel):
    name: str = pyd.Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: str
    description: str | None = None
    required: bool = False
    nullable: bool = False
    default: DefaultValue | _Unset = UNSET
    constraints: Constraints | None = None
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer("default")
    def _serialize_default(self, value: object, _info: object) -> object:
        # UNSET не сериализуется в JSON как значение; для JSON-схемы это null.
        return None if value is UNSET else value


class ExtendsRef(pyd.BaseModel):
    import_: str = pyd.Field(alias="import")
    entity: str

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class Entity(pyd.BaseModel):
    name: str = pyd.Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    version: str | int | None = None
    updated_at: date | datetime | None = None
    extends: str | ExtendsRef | None = None
    fields: tuple[FieldDef, ...] = ()
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class EnumValue(pyd.BaseModel):
    name: str = pyd.Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str | int | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class EnumDef(pyd.BaseModel):
    name: str = pyd.Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    values: tuple[EnumValue, ...] = ()
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CustomType(pyd.BaseModel):
    name: str = pyd.Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    base: str
    constraints: Constraints | None = None
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class _IndexedModel(pyd.BaseModel):
    """Immutable модель с индексами по именам."""

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
    pass


class SourceModel(ModelSlice):
    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = pyd.Field(default_factory=dict)


class InputSelection(pyd.BaseModel):
    """Выбор подмножества модели; None/пусто = все."""

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
    "EnumDef",
    "EnumValue",
    "ExtendsRef",
    "FieldDef",
    "InputSelection",
    "ModelSlice",
    "SourceModel",
]
