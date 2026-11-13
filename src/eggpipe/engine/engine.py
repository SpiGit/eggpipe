"""Engine — библиотечный фасад."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from eggpipe.config.app_config import AppConfig
from eggpipe.config.generator_rules import GeneratorConfig, GeneratorRules
from eggpipe.core.composition import Composition, CompositionResult
from eggpipe.core.discovery import SourceGroup, discover_sources
from eggpipe.core.document import ModelDocument
from eggpipe.core.parser import Parser
from eggpipe.core.slicing import select_slice
from eggpipe.core.validator import validate_entity_model
from eggpipe.engine.artifact_writer import ArtifactWriter, ExecutionPlan
from eggpipe.engine.format_registry import FormatRegistry
from eggpipe.engine.plugin_loader import build_format_registry, load_generators
from eggpipe.engine.report import (
    ArtifactReport,
    EngineReport,
    GeneratorReport,
)
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning
from eggpipe.interfaces.formats import EntityModelFormat
from eggpipe.interfaces.generator import (
    GenerationContext,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
)
from eggpipe.utils.exceptions import (
    ConfigValidationError,
    DocumentError,
    LockError,
    ManifestError,
)
from eggpipe.version import __version__


@dataclass
class _Pending:
    config: GeneratorConfig
    plugin: GeneratorPlugin
    result: GenerationResult
    plan: ExecutionPlan
    output_dir: Path
    format_name: str
    format_version: str


@dataclass
class _GeneratorRun:
    generators: list[GeneratorReport]
    artifacts: list[ArtifactReport]
    pending: list[_Pending]
    diagnostics: list[Diagnostic]


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
        self.registry = formats or build_format_registry()
        self.parser = Parser(self.registry)
        self.generators = dict(generators) if generators is not None else load_generators()
        self.source_paths = source_paths
        self.variables = {**rules.variables, **(variables or {})}
        self.writer = ArtifactWriter(eggpipe_version=__version__)
        self.run_id = uuid.uuid4().hex
        self._pending: list[_Pending] = []

    def build(self) -> EngineReport:
        started = time.perf_counter()
        self._pending = []
        diagnostics: list[Diagnostic] = []
        sources, source_groups = self._source_paths(diagnostics)
        if not sources:
            return self._report(False, 1, diagnostics, [], started)

        composition = self._load_composition(sources, source_groups, diagnostics)
        if composition is None:
            return self._report(False, 1, diagnostics, [], started)

        self._validate_model(composition, diagnostics)
        diagnostics = self._filter_ignored(diagnostics)
        if _has_errors(diagnostics):
            return self._report(False, 1, diagnostics, [], started)

        run = self._run_generators(composition)
        diagnostics.extend(run.diagnostics)
        self._pending = run.pending
        success = not _has_errors(diagnostics)
        return self._report(
            success,
            0 if success else 1,
            self._filter_ignored(diagnostics),
            run.generators,
            started,
            run.artifacts,
        )

    def _load_composition(
        self,
        sources: list[Path],
        source_groups: list[SourceGroup] | None,
        diagnostics: list[Diagnostic],
    ) -> CompositionResult | None:
        composition = Composition(
            self.parser,
            project_root=self.config_dir,
            allow_outside=self.config.allow_outside_imports,
        )
        try:
            result = composition.resolve(sources, source_groups)
        except DocumentError as exc:
            diagnostics.append(error(exc.code, exc.message, file=exc.path))
            return None
        diagnostics.extend(result.diagnostics)
        if self.rules.diagnostics.stale_dates:
            diagnostics.extend(_stale_date_diagnostics(result.documents))
        return result

    def _validate_model(
        self,
        composition: CompositionResult,
        diagnostics: list[Diagnostic],
    ) -> None:
        format_plugin = self.registry.get(composition.format)
        diagnostics.extend(
            validate_entity_model(
                composition.model,
                primitive_types=format_plugin.primitive_types,
            )
        )
        if isinstance(format_plugin, EntityModelFormat):
            return
        for document in composition.documents:
            diagnostics.extend(format_plugin.validate(document))

    def _run_generators(self, composition: CompositionResult) -> _GeneratorRun:
        run = _GeneratorRun(generators=[], artifacts=[], pending=[], diagnostics=[])
        for generator_config in self.rules.generators:
            if not generator_config.enabled and not self.config.include_disabled:
                continue
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                raise ConfigValidationError(f"неизвестный генератор: {generator_config.id}")
            generator_started = time.perf_counter()
            result, plan = self._run_generator(composition, generator_config, plugin)
            run.diagnostics.extend(result.warnings)
            run.diagnostics.extend(result.errors)
            run.diagnostics.extend(plan.diagnostics)
            status = "ok" if result.success and not plan.has_errors else "error"
            artifact_reports = [
                ArtifactReport(
                    path=str(item.path),
                    status=item.action,
                    sha256=item.sha256,
                )
                for item in plan.artifacts
            ]
            run.artifacts.extend(artifact_reports)
            run.generators.append(
                GeneratorReport(
                    id=generator_config.id,
                    status=status,
                    duration_ms=int((time.perf_counter() - generator_started) * 1000),
                    artifacts=artifact_reports,
                )
            )
            if status == "ok":
                run.pending.append(
                    _Pending(
                        config=generator_config,
                        plugin=plugin,
                        result=result,
                        plan=plan,
                        output_dir=self._output_dir(generator_config),
                        format_name=composition.format,
                        format_version=composition.version,
                    )
                )
        return run

    def generate(self) -> EngineReport:
        report = self.build()
        if not report.success:
            return report
        diagnostics = list(report.diagnostics)
        generators = list(report.generators)
        for pending in self._pending:
            try:
                cleanup = "enabled" if self.config.clean else pending.config.cleanup
                if cleanup == "prompt":
                    diagnostics.append(
                        warning(
                            "MG030",
                            "cleanup: prompt без tty; используется off",
                            path=str(pending.output_dir),
                        )
                    )
                    cleanup = "off"
                with self.writer.write_lock(pending.output_dir):
                    diagnostics.extend(
                        self.writer.write(
                            generator_id=pending.config.id,
                            output_dir=pending.output_dir,
                            plan=pending.plan,
                            plugin_version=_plugin_version(pending.plugin),
                            format_name=pending.format_name,
                            format_version=pending.format_version,
                            cleanup=cleanup,
                        )
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

    def _source_paths(
        self, diagnostics: list[Diagnostic]
    ) -> tuple[list[Path], list[SourceGroup] | None]:
        if self.source_paths is not None:
            return (
                [
                    path if path.is_absolute() else (self.config_dir / path).resolve()
                    for path in self.source_paths
                ],
                None,
            )
        if not self.rules.sources:
            raise ConfigValidationError("в .eggpipe.yaml нет sources")
        discovered = discover_sources(self.rules, self.config_dir)
        diagnostics.extend(discovered.diagnostics)
        return discovered.paths, discovered.groups

    def _run_generator(
        self,
        composition: CompositionResult,
        generator_config: GeneratorConfig,
        plugin: GeneratorPlugin,
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
        slice_, slice_diagnostics = select_slice(composition.model, generator_config.input)
        context = GenerationContext(
            variables=dict(self.variables),
            naming_hint=self.rules.defaults.naming_convention,
            imports=dict(composition.imports),
            sources=[document.path for document in composition.documents],
            formats=slice_.formats,
            run_id=self.run_id,
            config_dir=self.config_dir,
        )
        config_errors, config_warnings = _partition(config_diagnostics)
        slice_errors, slice_warnings = _partition(slice_diagnostics)
        errors = config_errors + slice_errors
        if errors:
            return (
                GenerationResult(
                    warnings=config_warnings + slice_warnings,
                    errors=errors,
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
        warnings = config_warnings + slice_warnings
        if warnings:
            result = result.model_copy(update={"warnings": [*warnings, *result.warnings]})
        if not result.success:
            return result, ExecutionPlan()
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

    def _filter_ignored(self, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
        ignored = self.rules.diagnostics.ignore
        return [item for item in diagnostics if item.code not in ignored]

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


def _plugin_version(plugin: GeneratorPlugin) -> str:
    return str(getattr(plugin, "__version__", "1"))


def _stale_date_diagnostics(
    documents: tuple[ModelDocument, ...],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for document in documents:
        file_date = datetime.fromtimestamp(document.path.stat().st_mtime, tz=UTC).date()
        for entity in document.model.entities:
            if entity.updated_at is None:
                continue
            updated: date = (
                entity.updated_at.date()
                if isinstance(entity.updated_at, datetime)
                else entity.updated_at
            )
            if updated < file_date:
                diagnostics.append(
                    warning(
                        "MG014",
                        f"updated_at {updated.isoformat()} старше mtime {file_date.isoformat()}",
                        file=document.path,
                        entity=entity.name,
                    )
                )
    return diagnostics


def _partition(
    diagnostics: list[Diagnostic],
) -> tuple[list[Diagnostic], list[Diagnostic]]:
    errors = [item for item in diagnostics if item.level == "error"]
    warnings = [item for item in diagnostics if item.level == "warning"]
    return errors, warnings


def _has_errors(diagnostics: list[Diagnostic]) -> bool:
    return any(item.level == "error" for item in diagnostics)


__all__ = ["Engine"]
