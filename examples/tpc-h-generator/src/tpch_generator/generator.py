"""TPC-H generators: DDL and Pydantic models (decorator API)."""

from __future__ import annotations

from pathlib import Path

from eggpipe import (
    Artifact,
    GenerationContext,
    GeneratorConfig,
    ModelSlice,
    generator,
)
from tpch_generator.ddl import render_ddl
from tpch_generator.pydantic_models import render_pydantic


def _schema(config: GeneratorConfig) -> str:
    value = config.options.get("schema", "public")
    return value if isinstance(value, str) else "public"


def _templates_dir(config: GeneratorConfig, context: GenerationContext) -> Path | None:
    value = config.options.get("templates_dir")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("options.templates_dir must be a non-empty string")
    path = Path(value)
    if not path.is_absolute():
        path = context.config_dir / path
    return path


def _ddl_artifact(
    model: ModelSlice,
    config: GeneratorConfig,
    context: GenerationContext,
) -> Artifact:
    return Artifact(
        path="postgres/schema.sql",
        content=render_ddl(model, _schema(config), _templates_dir(config, context)),
    )


def _pydantic_artifact(
    model: ModelSlice,
    config: GeneratorConfig,
    context: GenerationContext,
) -> Artifact:
    return Artifact(
        path="python/tpch_models.py",
        content=render_pydantic(model, _templates_dir(config, context)),
    )


@generator(
    id="tpch",
    name="TPC-H DDL + Pydantic",
    input_formats={"entity-model"},
)
def tpch(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [
        _ddl_artifact(model, config, context),
        _pydantic_artifact(model, config, context),
    ]


@generator(
    id="tpch-ddl",
    name="TPC-H PostgreSQL DDL",
    input_formats={"entity-model"},
)
def tpch_ddl(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [_ddl_artifact(model, config, context)]


@generator(
    id="tpch-pydantic",
    name="TPC-H Pydantic models",
    input_formats={"entity-model"},
)
def tpch_pydantic(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [_pydantic_artifact(model, config, context)]


TpchGenerator = tpch
TpchDdlGenerator = tpch_ddl
TpchPydanticGenerator = tpch_pydantic

__all__ = ["TpchDdlGenerator", "TpchGenerator", "TpchPydanticGenerator"]
