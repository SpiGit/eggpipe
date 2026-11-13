"""Подготовка данных TPC-H для Jinja2-шаблона PostgreSQL DDL."""

from __future__ import annotations

from pathlib import Path

from eggpipe import ModelSlice
from eggpipe.templating import jinja_environment, render_template
from tpch_generator.metadata import field_sql_type, table_info


def render_ddl(
    model: ModelSlice,
    schema: str = "public",
    templates_dir: Path | None = None,
) -> str:
    tables = []
    for entity in model.entities:
        table = table_info(entity)
        tables.append(
            {
                "name": table.name,
                "columns": [
                    {
                        "name": field.name,
                        "sql_type": field_sql_type(field),
                        "nullable": field.nullable,
                    }
                    for field in entity.fields
                ],
                "primary_key": list(table.primary_key),
                "foreign_keys": [
                    {
                        "columns": list(foreign_key.columns),
                        "table": foreign_key.table,
                        "references": list(foreign_key.references),
                    }
                    for foreign_key in table.foreign_keys
                ],
            }
        )
    environment = jinja_environment(package="tpch_generator", templates_dir=templates_dir)
    return render_template(environment, "schema.sql.j2", schema=schema, tables=tables)
