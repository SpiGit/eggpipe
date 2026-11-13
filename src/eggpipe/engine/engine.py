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
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.core.model import FormatInfo, ModelSlice
from eggpipe.core.parser import Parser
from eggpipe.core.slicing import select_slice
from eggpipe.core.validator import validate_entity_model
from eggpipe.engine.artifact_writer import ArtifactWriter, ExecutionPlan, LocationKey
from eggpipe.engine.plugin_loader import build_format_registry, load_generators
from eggpipe.engine.policy import DiagnosticPolicy
from eggpipe.engine.report import (
    ArtifactReport,
    EngineReport,
    FormatReport,
    FormatSummary,
    GeneratorReport,
    ManifestLocationSummary,
    ManifestSummary,
    StaleLocation,
)
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning
from eggpipe.interfaces.formats import EntityModelFormat
from eggpipe.interfaces.generator import (
    GenerationContext,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    ImportedFile,
)
from eggpipe.utils.exceptions import (
    ConfigValidationError,
    DocumentError,
    LockError,
    ManifestError,
)
from eggpipe.version import __version__


@dataclass(frozen=True)
class _Pending:
    config: GeneratorConfig
    plugin: GeneratorPlugin
    result: GenerationResult
    plan: ExecutionPlan
    output_dir: Path


@dataclass(frozen=True)
class _GeneratorRun:
    generators: tuple[GeneratorReport, ...]
    artifacts: tuple[ArtifactReport, ...]
    pending: tuple[_Pending, ...]
    diagnostics: tuple[Diagnostic, ...]


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
        self.writer = ArtifactWriter(eggpipe_version=__version__, config_dir=self.config_dir)
        self.policy = DiagnosticPolicy(self.rules.diagnostics.ignore)
        self.run_id = uuid.uuid4().hex
        self._pending: list[_Pending] = []
        self._formats: list[FormatSummary] = []
        self._stale: list[StaleLocation] = []
        self._stale_paths: set[Path] = set()
        self._timings: dict[str, int] = {}
        self._started = 0.0

    def build(self) -> EngineReport:
        started = time.perf_counter()
        self._started = started
        self._timings = _empty_timings()
        self._pending = []
        self._formats = []
        self._stale = []
        self._stale_paths = set()
        diagnostics: list[Diagnostic] = []
        phase = time.perf_counter()
        sources, source_groups, resources = self._source_paths(diagnostics)
        self._timings["discovery_ms"] = _elapsed(phase)
        if not sources:
            return self._report(False, 1, diagnostics, [], started)

        phase = time.perf_counter()
        composition = self._load_composition(sources, source_groups, resources, diagnostics)
        self._timings["parse_ms"] = _elapsed(phase)
        if composition is None:
            return self._report(False, 1, diagnostics, [], started)

        phase = time.perf_counter()
        self._formats = _format_summaries(composition)
        self._validate_model(composition, diagnostics)
        self._timings["validate_ms"] = _elapsed(phase)
        diagnostics = self._filter_ignored(diagnostics)
        if _has_errors(diagnostics):
            return self._report(False, 1, diagnostics, [], started)

        phase = time.perf_counter()
        run = self._run_generators(composition)
        self._timings["generate_ms"] = _elapsed(phase)
        diagnostics.extend(run.diagnostics)
        self._pending = list(run.pending)
        if not any(item.code == "MG052" for item in diagnostics):
            self._stale = self._stale_location_entries()
            diagnostics.extend(_stale_diagnostics(self._stale))
        success = not _has_errors(diagnostics)
        return self._report(
            success,
            _exit_code(success, diagnostics),
            self._filter_ignored(diagnostics),
            list(run.generators),
            started,
            list(run.artifacts),
        )

    def _load_composition(
        self,
        sources: list[Path],
        source_groups: list[SourceGroup] | None,
        resources: dict[str, ImportedFile],
        diagnostics: list[Diagnostic],
    ) -> CompositionResult | None:
        composition = Composition(
            self.parser,
            project_root=self.config_dir,
            allow_outside=self.config.allow_outside_imports,
        )
        try:
            result = composition.resolve(sources, source_groups, resources=resources)
        except DocumentError as exc:
            diagnostics.append(error(exc.code, exc.message, file=exc.path))
            return None
        diagnostics.extend(result.diagnostics)
        if self.rules.diagnostics.stale_dates:
            diagnostics.extend(_stale_date_diagnostics(result.documents, self._stale_paths))
        return result

    def _validate_model(
        self,
        composition: CompositionResult,
        diagnostics: list[Diagnostic],
    ) -> None:
        plugins = [self.registry.get(document.format) for document in composition.documents]
        primitives: set[str] = set()
        for plugin in plugins:
            primitives.update(plugin.primitive_types)
        if not primitives:
            primitives.update(self.registry.get(composition.format).primitive_types)
        diagnostics.extend(
            validate_entity_model(
                composition.model,
                primitive_types=primitives,
            )
        )
        for document, plugin in zip(composition.documents, plugins, strict=True):
            if isinstance(plugin, EntityModelFormat):
                continue
            diagnostics.extend(plugin.validate(document))

    def _run_generators(self, composition: CompositionResult) -> _GeneratorRun:
        generators: list[GeneratorReport] = []
        artifacts: list[ArtifactReport] = []
        pending: list[_Pending] = []
        diagnostics: list[Diagnostic] = []
        claimed: dict[str, LocationKey] = {}
        for generator_config in self.rules.generators:
            if not generator_config.enabled and not self.config.include_disabled:
                continue
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                raise ConfigValidationError(f"неизвестный генератор: {generator_config.id}")
            generator_started = time.perf_counter()
            result, plan = self._run_generator(composition, generator_config, plugin)
            plan.diagnostics.extend(
                _claim_paths(
                    plan,
                    self.writer.location_key(
                        generator_config.id,
                        self._output_dir(generator_config),
                    ),
                    claimed,
                )
            )
            diagnostics.extend(result.warnings)
            diagnostics.extend(result.errors)
            diagnostics.extend(plan.diagnostics)
            status = "ok" if result.success and not plan.has_errors else "error"
            artifact_reports = [
                ArtifactReport(
                    generator=generator_config.id,
                    path=str(item.path),
                    action=item.action,
                    sha256=item.sha256,
                )
                for item in plan.artifacts
            ]
            artifacts.extend(artifact_reports)
            generators.append(
                GeneratorReport(
                    id=generator_config.id,
                    name=plugin.name or generator_config.id,
                    status=status,
                    input_formats=_input_formats(plugin),
                    formats=_format_reports(plan.formats),
                    duration_ms=int((time.perf_counter() - generator_started) * 1000),
                )
            )
            if status == "ok":
                pending.append(
                    _Pending(
                        config=generator_config,
                        plugin=plugin,
                        result=result,
                        plan=plan,
                        output_dir=self._output_dir(generator_config),
                    )
                )
        return _GeneratorRun(
            generators=tuple(generators),
            artifacts=tuple(artifacts),
            pending=tuple(pending),
            diagnostics=tuple(diagnostics),
        )

    def generate(self) -> EngineReport:
        try:
            with self.writer.write_lock():
                report = self.build()
                if not report.success:
                    return report
                return self._write_pending(report)
        except LockError as exc:
            return self._report(
                False,
                1,
                [error("MG300", f"не удалось взять lock: {exc}")],
                [],
                time.perf_counter(),
            )

    def _write_pending(self, report: EngineReport) -> EngineReport:
        diagnostics = list(report.diagnostics)
        generators = list(report.generators)
        phase = time.perf_counter()
        try:
            for pending in self._pending:
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
                diagnostics.extend(
                    self.writer.write(
                        generator_id=pending.config.id,
                        output_dir=pending.output_dir,
                        plan=pending.plan,
                        plugin_version=_plugin_version(pending.plugin),
                        cleanup=cleanup,
                    )
                )
        except (ManifestError, OSError) as exc:
            diagnostics.append(error("MG300", f"не удалось записать артефакты: {exc}"))
            if self._pending:
                failed = {pending.config.id for pending in self._pending}
                generators = [
                    item.model_copy(update={"status": "error"}) if item.id in failed else item
                    for item in generators
                ]
        self._timings["write_ms"] = _elapsed(phase)
        success = not _has_errors(diagnostics)
        return report.model_copy(
            update={
                "success": success,
                "exit_code": 0 if success else 1,
                "diagnostics": diagnostics,
                "generators": generators,
                "manifest": self._manifest_summary(),
                "timings": self._timings_with_total(),
            }
        )

    def check(self) -> EngineReport:
        report = self.build()
        diagnostics = list(report.diagnostics)
        for pending in self._pending:
            diagnostics.extend(self.writer.check(plan=pending.plan))
        success = not _has_errors(diagnostics)
        return report.model_copy(
            update={
                "success": success,
                "exit_code": _exit_code(success, diagnostics),
                "diagnostics": diagnostics,
            }
        )

    def _stale_location_entries(self) -> list[StaleLocation]:
        try:
            manifest = self.writer.load_manifest()
        except ManifestError:
            return []
        configured = {
            self.writer.location_key(item.id, self._output_dir(item))
            for item in self.rules.generators
        }
        return [
            StaleLocation(generator=location.generator, output_dir=location.output_dir)
            for location in manifest.locations
            if location.key not in configured
        ]

    def _source_paths(
        self, diagnostics: list[Diagnostic]
    ) -> tuple[list[Path], list[SourceGroup] | None, dict[str, ImportedFile]]:
        if self.source_paths is not None:
            return (
                [
                    path if path.is_absolute() else (self.config_dir / path).resolve()
                    for path in self.source_paths
                ],
                None,
                {},
            )
        if not self.rules.sources:
            raise ConfigValidationError("в .eggpipe.yaml нет sources")
        discovered = discover_sources(
            self.rules,
            self.config_dir,
            allow_outside=self.config.allow_outside_imports,
        )
        diagnostics.extend(discovered.diagnostics)
        for group in discovered.groups:
            for unit in group.units or ():
                if unit.stale_dates:
                    self._stale_paths.update(unit.paths)
        return discovered.paths, discovered.groups, discovered.resources

    def _run_generator(
        self,
        composition: CompositionResult,
        generator_config: GeneratorConfig,
        plugin: GeneratorPlugin,
    ) -> tuple[GenerationResult, ExecutionPlan]:
        slice_, slice_diagnostics = select_slice(composition.model, generator_config.input)
        context = GenerationContext(
            variables=dict(self.variables),
            naming_hint=self.rules.defaults.naming_convention,
            imports=dict(composition.imports),
            sources=tuple(_composition_sources(composition)),
            formats=slice_.formats,
            run_id=self.run_id,
            config_dir=self.config_dir,
        )
        slice_errors, slice_warnings = _partition(slice_diagnostics)
        if slice_errors:
            return GenerationResult(warnings=slice_warnings, errors=slice_errors), ExecutionPlan()

        format_errors = _check_input_formats(plugin, generator_config.id, slice_, self.registry)
        if format_errors:
            return GenerationResult(warnings=slice_warnings, errors=format_errors), ExecutionPlan()

        try:
            config_diagnostics = plugin.validate_config(generator_config)
        except Exception as exc:
            return (
                GenerationResult(
                    warnings=slice_warnings,
                    errors=[
                        error(
                            "MG300",
                            f"validate_config {generator_config.id} упал: "
                            f"{type(exc).__name__}: {exc}",
                        )
                    ],
                ),
                ExecutionPlan(),
            )
        config_errors, config_warnings = _partition(config_diagnostics)
        warnings = slice_warnings + config_warnings
        if config_errors:
            return GenerationResult(warnings=warnings, errors=config_errors), ExecutionPlan()

        try:
            result = plugin.generate(
                GeneratorInput(model=slice_, config=generator_config, context=context)
            )
        except Exception as exc:
            return (
                GenerationResult(
                    warnings=warnings,
                    errors=[
                        error(
                            "MG300",
                            f"генератор {generator_config.id} упал: {type(exc).__name__}: {exc}",
                        )
                    ],
                ),
                ExecutionPlan(),
            )
        if warnings:
            result = result.model_copy(update={"warnings": [*warnings, *result.warnings]})
        if not result.success:
            return result, ExecutionPlan()
        try:
            plan = self.writer.plan(
                generator_id=generator_config.id,
                output_dir=self._output_dir(generator_config),
                artifacts=result.artifacts,
                on_conflict=generator_config.on_conflict,
                force=self.config.force,
                formats=slice_.formats,
            )
        except ManifestError as exc:
            return (
                GenerationResult(
                    warnings=warnings,
                    errors=[error("MG052", str(exc))],
                ),
                ExecutionPlan(),
            )
        return result, plan

    def _output_dir(self, generator_config: GeneratorConfig) -> Path:
        base = self.config.output_root or self.config_dir
        return (base / generator_config.output_dir).resolve()

    def _filter_ignored(self, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
        return self.policy.apply(diagnostics)

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
            formats=list(self._formats),
            generators=generators,
            artifacts=artifacts or [],
            manifest=self._manifest_summary(),
            stale_locations=list(self._stale),
            timings=self._timings_with_total(),
        )

    def _timings_with_total(self) -> dict[str, int]:
        return {
            **self._timings,
            "total_ms": _elapsed(self._started),
        }

    def _manifest_summary(self) -> ManifestSummary | None:
        try:
            manifest = self.writer.load_manifest()
        except ManifestError:
            return None
        return ManifestSummary(
            manifest_version=manifest.manifest_version,
            locations=[
                ManifestLocationSummary(
                    generator=location.generator,
                    output_dir=location.output_dir,
                    artifacts=len(location.artifacts),
                )
                for location in manifest.locations
            ],
        )


def _empty_timings() -> dict[str, int]:
    return {
        "discovery_ms": 0,
        "parse_ms": 0,
        "validate_ms": 0,
        "generate_ms": 0,
        "write_ms": 0,
    }


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _plugin_version(plugin: GeneratorPlugin) -> str:
    return str(getattr(plugin, "__version__", "unknown"))


def _stale_date_diagnostics(
    documents: tuple[ModelDocument, ...],
    allowed_paths: set[Path],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for document in documents:
        if document.path not in allowed_paths:
            continue
        try:
            modified = document.path.stat().st_mtime
        except OSError:
            continue
        file_date = datetime.fromtimestamp(modified, tz=UTC).date()
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


def _composition_sources(composition: CompositionResult) -> list[Path]:
    paths = {document.path for document in composition.documents}
    for document in composition.documents:
        for entity in document.model.entities:
            paths.update(entity.layer_sources)
    return sorted(paths, key=lambda item: item.as_posix())


def _format_summaries(composition: CompositionResult) -> list[FormatSummary]:
    counts: dict[tuple[str, str], int] = {}
    for entity in composition.model.entities:
        name = entity.format or composition.format
        version = entity.format_version or composition.version
        counts[(name, version)] = counts.get((name, version), 0) + 1
    return [
        FormatSummary(name=name, version=version, entities=count)
        for (name, version), count in sorted(counts.items())
    ]


def _format_reports(formats: frozenset[FormatInfo]) -> list[FormatReport]:
    return [
        FormatReport(name=item.name, version=item.version)
        for item in sorted(formats, key=lambda item: (item.name, item.version))
    ]


def _input_formats(plugin: GeneratorPlugin) -> list[str] | None:
    formats = getattr(type(plugin), "input_formats", None)
    return None if formats is None else sorted(formats)


def _stale_diagnostics(stale: list[StaleLocation]) -> list[Diagnostic]:
    return [
        warning(
            "MG051",
            "stale generated location в manifest",
            path=item.output_dir,
        )
        for item in stale
    ]


def _claim_paths(
    plan: ExecutionPlan,
    location: LocationKey,
    claimed: dict[str, LocationKey],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for item in plan.artifacts:
        name = item.target.resolve().as_posix().casefold()
        for other, owner in claimed.items():
            if owner == location:
                continue
            if name == other or name.startswith(f"{other}/") or other.startswith(f"{name}/"):
                diagnostics.append(
                    error(
                        "MG042",
                        f"path {item.path} уже занят location {owner.generator}:{owner.output_dir}",
                        path=str(item.path),
                    )
                )
                break
        claimed[name] = location
    return diagnostics


def _check_input_formats(
    plugin: GeneratorPlugin,
    generator_id: str,
    slice_: ModelSlice,
    registry: FormatRegistry,
) -> list[Diagnostic]:
    if not slice_.entities:
        return []
    missing = object()
    accepted = getattr(type(plugin), "input_formats", missing)
    if accepted is missing:
        return [error("MG301", f"генератор {generator_id}: input_formats обязателен")]
    if accepted is not None and not isinstance(accepted, set):
        return [error("MG301", f"генератор {generator_id}: input_formats должен быть set[str]")]
    errors: list[Diagnostic] = []
    for entity in slice_.entities:
        if entity.format is None:
            continue
        if not registry.accepts(entity.format, accepted):
            errors.append(
                error(
                    "MG033",
                    f"генератор {generator_id} не поддерживает формат {entity.format}",
                    entity=entity.name,
                )
            )
    return errors


def _partition(
    diagnostics: list[Diagnostic],
) -> tuple[list[Diagnostic], list[Diagnostic]]:
    errors = [item for item in diagnostics if item.level == "error"]
    warnings = [item for item in diagnostics if item.level == "warning"]
    return errors, warnings


def _has_errors(diagnostics: list[Diagnostic]) -> bool:
    return any(item.level == "error" for item in diagnostics)


def _exit_code(success: bool, diagnostics: list[Diagnostic]) -> int:
    if success:
        return 0
    return 2 if any(item.code == "MG033" for item in diagnostics) else 1


__all__ = ["Engine"]
