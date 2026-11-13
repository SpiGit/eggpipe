"""TPC-H генераторы: DDL и Pydantic модели (decorator API)."""

from __future__ import annotations

from pathlib import Path

from eggpipe import (
    Artifact,
    GenerationContext,
    GeneratorConfig,
    ModelSlice,
    generator,
)
from eggpipe.templating import TemplateError
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
        raise ValueError("options.templates_dir должен быть непустой строкой")
    path = Path(value)
    if not path.is_absolute():
        path = context.config_dir / path
    return path


def _render_ddl(
    model: ModelSlice,
    config: GeneratorConfig,
    context: GenerationContext,
) -> str:
    try:
        return render_ddl(model, _schema(config), _templates_dir(config, context))
    except (TemplateError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def _render_pydantic(
    model: ModelSlice,
    config: GeneratorConfig,
    context: GenerationContext,
) -> str:
    try:
        return render_pydantic(model, _templates_dir(config, context))
    except (TemplateError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


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
        Artifact(path="postgres/schema.sql", content=_render_ddl(model, config, context)),
        Artifact(path="python/tpch_models.py", content=_render_pydantic(model, config, context)),
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
    return [Artifact(path="postgres/schema.sql", content=_render_ddl(model, config, context))]


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
    return [
        Artifact(
            path="python/tpch_models.py",
            content=_render_pydantic(model, config, context),
        )
    ]


TpchGenerator = tpch
TpchDdlGenerator = tpch_ddl
TpchPydanticGenerator = tpch_pydantic

__all__ = ["TpchDdlGenerator", "TpchGenerator", "TpchPydanticGenerator"]
