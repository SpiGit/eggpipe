"""TPC-H генераторы: DDL и Pydantic модели."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override

from eggpipe import (
    Artifact,
    Diagnostic,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
)
from eggpipe.templating import TemplateError
from tpch_generator.ddl import render_ddl
from tpch_generator.pydantic_models import render_pydantic


class _TpchBase(GeneratorPlugin):
    @override
    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        schema = config.options.get("schema", "public")
        if not isinstance(schema, str) or not schema:
            return [
                Diagnostic(
                    level="error",
                    code="MG300",
                    message="options.schema должен быть непустой строкой",
                )
            ]
        if "templates_dir" in config.options and not isinstance(
            config.options["templates_dir"], str
        ):
            return [
                Diagnostic(
                    level="error",
                    code="MG300",
                    message="options.templates_dir должен быть строкой",
                )
            ]
        return []

    def _schema(self, input: GeneratorInput) -> str:
        value = input.config.options.get("schema", "public")
        return value if isinstance(value, str) else "public"

    def _templates_dir(self, input: GeneratorInput) -> Path | None:
        value = input.config.options.get("templates_dir")
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError("options.templates_dir должен быть непустой строкой")
        path = Path(value)
        if not path.is_absolute():
            path = input.context.config_dir / path
        return path

    def _render(self, input: GeneratorInput) -> GenerationResult:
        try:
            templates_dir = self._templates_dir(input)
            ddl = render_ddl(input.model, self._schema(input), templates_dir)
            models = render_pydantic(input.model, templates_dir)
        except (TemplateError, ValueError) as exc:
            return self._error(str(exc))
        return GenerationResult(
            artifacts=[
                Artifact(path="postgres/schema.sql", content=ddl),
                Artifact(path="python/tpch_models.py", content=models),
            ]
        )

    def _error(self, message: str) -> GenerationResult:
        return GenerationResult(errors=[Diagnostic(level="error", code="MG300", message=message)])


class TpchGenerator(_TpchBase):
    id = "tpch"
    name = "TPC-H DDL + Pydantic"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return self._render(input)


class TpchDdlGenerator(_TpchBase):
    id = "tpch-ddl"
    name = "TPC-H PostgreSQL DDL"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        try:
            content = render_ddl(input.model, self._schema(input), self._templates_dir(input))
        except (TemplateError, ValueError) as exc:
            return self._error(str(exc))
        return GenerationResult(artifacts=[Artifact(path="postgres/schema.sql", content=content)])


class TpchPydanticGenerator(_TpchBase):
    id = "tpch-pydantic"
    name = "TPC-H Pydantic models"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        try:
            content = render_pydantic(input.model, self._templates_dir(input))
        except (TemplateError, ValueError) as exc:
            return self._error(str(exc))
        return GenerationResult(artifacts=[Artifact(path="python/tpch_models.py", content=content)])


__all__ = ["TpchDdlGenerator", "TpchGenerator", "TpchPydanticGenerator"]
