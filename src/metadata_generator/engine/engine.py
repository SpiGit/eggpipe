"""Engine — библиотечный фасад."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from metadata_generator.config.app_config import AppConfig
from metadata_generator.config.generator_rules import GeneratorConfig, GeneratorRules
from metadata_generator.core.document import ModelDocument
from metadata_generator.core.model import SourceModel
from metadata_generator.core.parser import Parser
from metadata_generator.core.slicing import select_slice
from metadata_generator.core.validator import validate_document, validate_entity_model
from metadata_generator.engine.artifact_writer import ArtifactWriter, ExecutionPlan
from metadata_generator.engine.format_registry import FormatRegistry
from metadata_generator.engine.plugin_loader import load_generators
from metadata_generator.engine.report import (
    ArtifactReport,
    EngineReport,
    GeneratorReport,
)
from metadata_generator.interfaces.diagnostics import Diagnostic, error, warning
from metadata_generator.interfaces.generator import (
    GenerationContext,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
)
from metadata_generator.utils.exceptions import (
    ConfigValidationError,
    DocumentError,
    LockError,
    ManifestError,
)
from metadata_generator.version import __version__


@dataclass
class _Pending:
    config: GeneratorConfig
    plugin: GeneratorPlugin
    result: GenerationResult
    plan: ExecutionPlan
    output_dir: Path


class Engine:
    def __init__(
        self,
        config: AppConfig,
        rules: GeneratorRules,
        *,
        config_dir: Path | None = None,
        generators: Mapping[str, GeneratorPlugin] | None = None,
        formats: FormatRegistry | None = None,
        source_paths: list[Path] | None = None,
        variables: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.rules = rules
        self.config_dir = (config_dir or Path.cwd()).resolve()
        self.registry = formats or FormatRegistry()
        self.parser = Parser(self.registry)
        self.generators = dict(generators) if generators is not None else load_generators()
        self.source_paths = source_paths
        self.variables = {**rules.variables, **(variables or {})}
        self.writer = ArtifactWriter(mg_version=__version__)
        self.run_id = uuid.uuid4().hex
        self._pending: list[_Pending] = []
        self._documents: list[ModelDocument] = []

    def build(self) -> EngineReport:
        started = time.perf_counter()
        self._pending = []
        diagnostics: list[Diagnostic] = []
        documents = self._parse_sources(diagnostics)
        if not documents:
            return self._report(False, 1, diagnostics, [], started)
        self._documents = documents
        formats = {document.format for document in documents}
        if len(formats) != 1:
            diagnostics.append(
                error("MG007", "в одном запуске смешаны форматы: " + ", ".join(sorted(formats)))
            )
        versions = {(document.format, document.version) for document in documents}
        if len(versions) != 1:
            diagnostics.append(error("MG008", "в одном запуске смешаны версии формата"))
        model = _merge_documents(documents)
        diagnostics.extend(validate_entity_model(model))
        for document in documents:
            diagnostics.extend(item for item in validate_document(document) if item.code == "MG030")
        if _has_errors(diagnostics):
            return self._report(False, 1, diagnostics, [], started)

        generators: list[GeneratorReport] = []
        artifacts: list[ArtifactReport] = []
        for generator_config in self.rules.generators:
            if not generator_config.enabled and not self.config.include_disabled:
                continue
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                raise ConfigValidationError(f"неизвестный генератор: {generator_config.id}")
            generator_started = time.perf_counter()
            result, plan = self._run_generator(generator_config, plugin, model, documents)
            diagnostics.extend(result.warnings)
            diagnostics.extend(result.errors)
            diagnostics.extend(plan.diagnostics)
            status = "ok" if result.success and not plan.has_errors else "error"
            artifact_reports = [
                ArtifactReport(
                    path=str(item.path),
                    status=item.action,
                    sha256=item.sha256,
                )
                for item in plan.artifacts
            ]
            artifacts.extend(artifact_reports)
            generators.append(
                GeneratorReport(
                    id=generator_config.id,
                    status=status,
                    duration_ms=int((time.perf_counter() - generator_started) * 1000),
                    artifacts=artifact_reports,
                )
            )
            if status == "ok":
                output_dir = self._output_dir(generator_config)
                self._pending.append(
                    _Pending(
                        config=generator_config,
                        plugin=plugin,
                        result=result,
                        plan=plan,
                        output_dir=output_dir,
                    )
                )
        success = not _has_errors(diagnostics)
        return self._report(
            success, 0 if success else 1, diagnostics, generators, started, artifacts
        )

    def generate(self) -> EngineReport:
        report = self.build()
        if not report.success:
            return report
        diagnostics = list(report.diagnostics)
        generators = list(report.generators)
        for pending in self._pending:
            try:
                with self.writer.write_lock(pending.output_dir):
                    self.writer.write(
                        generator_id=pending.config.id,
                        output_dir=pending.output_dir,
                        plan=pending.plan,
                        plugin_version=_plugin_version(pending.plugin),
                        format_name=_format_name(self._documents),
                        format_version=_format_version(self._documents),
                    )
            except (LockError, ManifestError, OSError) as exc:
                diagnostics.append(
                    error(
                        "MG300",
                        f"не удалось записать {pending.config.id}: {exc}",
                        path=str(pending.output_dir),
                    )
                )
                generators = [
                    item.model_copy(update={"status": "error"})
                    if item.id == pending.config.id
                    else item
                    for item in generators
                ]
        success = not _has_errors(diagnostics)
        return report.model_copy(
            update={
                "success": success,
                "exit_code": 0 if success else 1,
                "diagnostics": diagnostics,
                "generators": generators,
            }
        )

    def check(self) -> EngineReport:
        report = self.build()
        diagnostics = list(report.diagnostics)
        for pending in self._pending:
            diagnostics.extend(self.writer.check(output_dir=pending.output_dir, plan=pending.plan))
        success = not _has_errors(diagnostics)
        return report.model_copy(
            update={
                "success": success,
                "exit_code": 0 if success else 1,
                "diagnostics": diagnostics,
            }
        )

    def _parse_sources(self, diagnostics: list[Diagnostic]) -> list[ModelDocument]:
        paths = self.source_paths or [self.config_dir / item.path for item in self.rules.sources]
        if not paths:
            raise ConfigValidationError("в .mg.yaml нет sources")
        documents: list[ModelDocument] = []
        for path in paths:
            source = path if path.is_absolute() else (self.config_dir / path)
            try:
                documents.append(self.parser.parse_document(source.resolve()))
            except DocumentError as exc:
                diagnostics.append(error(exc.code, exc.message, path=str(exc.path or source)))
        return documents

    def _run_generator(
        self,
        generator_config: GeneratorConfig,
        plugin: GeneratorPlugin,
        model: SourceModel,
        documents: list[ModelDocument],
    ) -> tuple[GenerationResult, ExecutionPlan]:
        try:
            config_diagnostics = plugin.validate_config(generator_config)
        except Exception as exc:
            return (
                GenerationResult(
                    errors=[
                        error(
                            "MG300",
                            f"validate_config {generator_config.id} упал: "
                            f"{type(exc).__name__}: {exc}",
                        )
                    ]
                ),
                ExecutionPlan(),
            )
        slice_, slice_diagnostics = select_slice(model, generator_config.input)
        context = GenerationContext(
            variables=dict(self.variables),
            naming_hint=self.rules.defaults.naming_convention,
            sources=[document.path for document in documents],
            format=_format_name(documents),
            format_version=_format_version(documents),
            run_id=self.run_id,
            config_dir=self.config_dir,
        )
        config_errors = [item for item in config_diagnostics if item.level == "error"]
        config_warnings = [item for item in config_diagnostics if item.level == "warning"]
        slice_errors = [item for item in slice_diagnostics if item.level == "error"]
        slice_warnings = [item for item in slice_diagnostics if item.level == "warning"]
        if config_errors or slice_errors:
            return (
                GenerationResult(
                    warnings=config_warnings + slice_warnings,
                    errors=config_errors + slice_errors,
                ),
                ExecutionPlan(),
            )
        try:
            result = plugin.generate(
                GeneratorInput(model=slice_, config=generator_config, context=context)
            )
        except Exception as exc:
            return (
                GenerationResult(
                    errors=[
                        error(
                            "MG300",
                            f"генератор {generator_config.id} упал: {type(exc).__name__}: {exc}",
                        )
                    ]
                ),
                ExecutionPlan(),
            )
        if config_warnings or slice_warnings:
            result = result.model_copy(
                update={"warnings": [*config_warnings, *slice_warnings, *result.warnings]}
            )
        if not result.success:
            return result, ExecutionPlan()
        if generator_config.cleanup != "off":
            result = result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        warning(
                            "MG030",
                            "cleanup появится в следующей версии; параметр проигнорирован",
                        ),
                    ]
                }
            )
        plan = self.writer.plan(
            generator_id=generator_config.id,
            output_dir=self._output_dir(generator_config),
            artifacts=result.artifacts,
            on_conflict=generator_config.on_conflict,
            force=self.config.force,
        )
        return result, plan

    def _output_dir(self, generator_config: GeneratorConfig) -> Path:
        base = self.config.output_root or self.config_dir
        return (base / generator_config.output_dir).resolve()

    def _report(
        self,
        success: bool,
        exit_code: int,
        diagnostics: list[Diagnostic],
        generators: list[GeneratorReport],
        started: float,
        artifacts: list[ArtifactReport] | None = None,
    ) -> EngineReport:
        return EngineReport(
            success=success,
            exit_code=exit_code,
            run_id=self.run_id,
            diagnostics=diagnostics,
            generators=generators,
            artifacts=artifacts or [],
            timings={"total_ms": int((time.perf_counter() - started) * 1000)},
        )


def _merge_documents(documents: list[ModelDocument]) -> SourceModel:
    entities = tuple(entity for document in documents for entity in document.model.entities)
    enums = tuple(item for document in documents for item in document.model.enums)
    types = tuple(item for document in documents for item in document.model.types)
    return SourceModel(entities=entities, enums=enums, types=types)


def _format_name(documents: list[ModelDocument]) -> str:
    return documents[0].format if documents else ""


def _format_version(documents: list[ModelDocument]) -> str:
    return documents[0].version if documents else ""


def _plugin_version(plugin: GeneratorPlugin) -> str:
    return str(getattr(plugin, "__version__", "1"))


def _has_errors(diagnostics: list[Diagnostic]) -> bool:
    return any(item.level == "error" for item in diagnostics)


__all__ = ["Engine"]
