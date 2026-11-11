"""Внутренние immutable-модели ядра."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_serializer,
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
    """Sentinel для «значение не задано»."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()

DefaultValue = str | int | float | bool | date | datetime | None


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

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer("default")
    def _serialize_default(self, value: object, _info: object) -> object:
        # UNSET не сериализуется в JSON как значение; ключ удаляется model_serializer.
        return None if value is UNSET else value

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


class Entity(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    version: str | int | None = None
    updated_at: date | datetime | None = None
    extends: str | ExtendsRef | None = None
    fields: tuple[FieldDef, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: Path | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(extra="forbid", frozen=True)


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputSelection(BaseModel):
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
