"""Чтение Postgres-метаданных из TPC-H модели."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def table_info(entity: Any) -> Table:
    metadata = entity.metadata.get("postgres")
    if not isinstance(metadata, dict):
        raise ValueError(f"entity {entity.name}: отсутствует metadata.postgres")
    table = metadata.get("table")
    if not isinstance(table, str) or not table:
        raise ValueError(f"entity {entity.name}: metadata.postgres.table обязателен")
    primary_key = metadata.get("primary_key", [])
    if not isinstance(primary_key, list) or not all(isinstance(item, str) for item in primary_key):
        raise ValueError(f"entity {entity.name}: primary_key должен быть списком строк")
    foreign_keys = []
    raw_foreign_keys = metadata.get("foreign_keys", [])
    if not isinstance(raw_foreign_keys, list):
        raise ValueError(f"entity {entity.name}: foreign_keys должен быть списком")
    for item in raw_foreign_keys:
        if not isinstance(item, dict):
            raise ValueError(f"entity {entity.name}: foreign_key должен быть словарём")
        columns = item.get("columns")
        references = item.get("references")
        if not isinstance(columns, list) or not isinstance(references, dict):
            raise ValueError(f"entity {entity.name}: некорректный foreign_key")
        ref_table = references.get("table")
        ref_columns = references.get("columns")
        if not isinstance(ref_table, str) or not isinstance(ref_columns, list):
            raise ValueError(f"entity {entity.name}: некорректный references")
        foreign_keys.append(
            ForeignKey(
                columns=tuple(str(column) for column in columns),
                table=ref_table,
                references=tuple(str(column) for column in ref_columns),
            )
        )
    return Table(
        name=table,
        primary_key=tuple(str(column) for column in primary_key),
        foreign_keys=tuple(foreign_keys),
    )


def field_sql_type(field: Any) -> str:
    metadata = field.metadata.get("postgres")
    if not isinstance(metadata, dict):
        raise ValueError(f"field {field.name}: отсутствует metadata.postgres")
    sql_type = metadata.get("type")
    if not isinstance(sql_type, str) or not sql_type:
        raise ValueError(f"field {field.name}: metadata.postgres.type обязателен")
    return sql_type
