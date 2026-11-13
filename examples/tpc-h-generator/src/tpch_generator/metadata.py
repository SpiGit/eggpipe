"""Чтение Postgres-метаданных из TPC-H модели."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eggpipe import Entity, FieldDef


@dataclass(frozen=True)
class ForeignKey:
    columns: tuple[str, ...]
    table: str
    references: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    name: str
    primary_key: tuple[str, ...]
    foreign_keys: tuple[ForeignKey, ...]


class _References(BaseModel):
    table: str = Field(min_length=1)
    columns: tuple[str, ...]

    model_config = ConfigDict(extra="ignore", frozen=True)


class _ForeignKey(BaseModel):
    columns: tuple[str, ...]
    references: _References

    model_config = ConfigDict(extra="ignore", frozen=True)


class _PostgresTable(BaseModel):
    table: str = Field(min_length=1)
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[_ForeignKey, ...] = ()

    model_config = ConfigDict(extra="ignore", frozen=True)


class _PostgresField(BaseModel):
    type: str = Field(min_length=1)

    model_config = ConfigDict(extra="ignore", frozen=True)


def table_info(entity: Entity) -> Table:
    metadata = _postgres_metadata(entity.metadata, f"entity {entity.name}")
    try:
        model = _PostgresTable.model_validate(metadata)
    except ValidationError as exc:
        raise ValueError(f"entity {entity.name}: {exc}") from exc
    return Table(
        name=model.table,
        primary_key=model.primary_key,
        foreign_keys=tuple(
            ForeignKey(
                columns=item.columns,
                table=item.references.table,
                references=item.references.columns,
            )
            for item in model.foreign_keys
        ),
    )


def field_sql_type(field: FieldDef) -> str:
    metadata = _postgres_metadata(field.metadata, f"field {field.name}")
    try:
        return _PostgresField.model_validate(metadata).type
    except ValidationError as exc:
        raise ValueError(f"field {field.name}: {exc}") from exc


def _postgres_metadata(metadata: dict[str, object], label: str) -> object:
    value = metadata.get("postgres")
    if not isinstance(value, dict):
        raise ValueError(f"{label}: отсутствует metadata.postgres")
    return value
