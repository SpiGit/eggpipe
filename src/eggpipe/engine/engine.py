"""Engine — library facade."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from eggpipe.config.app_config import AppConfig
from eggpipe.config.logging import get_logger
from eggpipe.config.project_config import GeneratorConfig, ProjectConfig
from eggpipe.core.composition import Composition, CompositionResult
from eggpipe.core.discovery import SourceGroup, discover_sources
from eggpipe.core.document import ModelDocument
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.core.model import PRIMITIVE_TYPES, FormatInfo, ModelSlice
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
from eggpipe.utils.yaml import YamlLoadError, parse_yaml
from eggpipe.version import __version__

_LOG = get_logger(__name__)


@dataclass(frozen=True)
class _Pending:
    config: GeneratorConfig
    plugin: GeneratorPlugin
    result: GenerationResult
    plan: ExecutionPlan
    output_dir: Path
    fingerprint: str | None = None


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
        rules: ProjectConfig,
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
        self._fingerprint: str | None = None
        self._incremental_reason: str | None = None
        self._entities: tuple[str, ...] | None = None

    def build(
        self,
        *,
        incremental: bool | None = None,
        entities: Collection[str] | None = None,
    ) -> EngineReport:
        started = time.perf_counter()
        self._started = started
        self._timings = _empty_timings()
        self._pending = []
        self._formats = []
        self._stale = []
        self._stale_paths = set()
        self._fingerprint = None
        self._incremental_reason = None
        if isinstance(entities, str):
            entities = (entities,)
        self._entities = tuple(dict.fromkeys(entities)) if entities is not None else None
        diagnostics: list[Diagnostic] = []
        phase = time.perf_counter()
        sources, source_groups, resources = self._source_paths(diagnostics)
        self._timings["discovery_ms"] = _elapsed(phase)
        if not sources:
            return self._report(False, 1, diagnostics, [], started)
        if self._entities is not None and not self._entities:
            diagnostics.append(error("EG018", "no entities selected", path="--entity"))
            return self._report(False, 1, self._filter_ignored(diagnostics), [], started)

        use_incremental = self.config.incremental if incremental is None else incremental
        if self._entities is not None:
            use_incremental = False
        if use_incremental:
            phase = time.perf_counter()
            self._fingerprint = self._input_fingerprint(sources, resources)
            self._timings["fingerprint_ms"] = _elapsed(phase)
            if self._fingerprint is not None:
                cached = self._cached_report(self._fingerprint, started, diagnostics)
                if cached is not None:
                    _LOG.debug("incremental cache hit")
                    return cached
            _LOG.debug(
                "incremental cache disabled: %s",
                self._incremental_reason or "input fingerprint changed or artifacts drifted",
            )

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

        if self._entities is not None:
            known = {entity.name for entity in composition.model.entities}
            missing = [name for name in self._entities if name not in known]
            if missing:
                diagnostics.extend(
                    error("EG018", f"unknown entity: {name}", entity=name) for name in missing
                )
                return self._report(False, 1, self._filter_ignored(diagnostics), [], started)
            scope_errors = self._output_scope_errors()
            if scope_errors:
                return self._report(False, 2, diagnostics + scope_errors, [], started)

        phase = time.perf_counter()
        run = self._run_generators(composition)
        self._timings["generate_ms"] = _elapsed(phase)
        diagnostics.extend(run.diagnostics)
        self._pending = list(run.pending)
        if not any(item.code == "EG052" for item in diagnostics):
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
            primitives.update(PRIMITIVE_TYPES)
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
                raise ConfigValidationError(f"unknown generator: {generator_config.id}")
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
                        fingerprint=self._fingerprint,
                    )
                )
        return _GeneratorRun(
            generators=tuple(generators),
            artifacts=tuple(artifacts),
            pending=tuple(pending),
            diagnostics=tuple(diagnostics),
        )

    def generate(self, *, entities: Collection[str] | None = None) -> EngineReport:
        try:
            with self.writer.write_lock():
                report = self.build(entities=entities)
                if not report.success:
                    return report
                return self._write_pending(report)
        except LockError as exc:
            return self._report(
                False,
                1,
                [error("EG300", f"failed to acquire the lock: {exc}")],
                [],
                time.perf_counter(),
            )

    def _write_pending(self, report: EngineReport) -> EngineReport:
        diagnostics = list(report.diagnostics)
        generators = list(report.generators)
        phase = time.perf_counter()
        try:
            per_entity = self._entities is not None
            for pending in self._pending:
                cleanup = "enabled" if self.config.clean else pending.config.cleanup
                if per_entity:
                    if cleanup != "off":
                        diagnostics.append(
                            warning(
                                "EG030",
                                "cleanup is ignored in per-entity mode",
                                path=str(pending.output_dir),
                            )
                        )
                    cleanup = "off"
                elif cleanup == "prompt":
                    diagnostics.append(
                        warning(
                            "EG030",
                            "cleanup: prompt without a tty; using off",
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
                        input_fingerprint=pending.fingerprint,
                        cleanup=cleanup,
                        merge=per_entity,
                    )
                )
        except (ManifestError, OSError) as exc:
            diagnostics.append(error("EG300", f"failed to write artifacts: {exc}"))
            if self._pending:
                failed = {pending.config.id for pending in self._pending}
                generators = [
                    item.model_copy(update={"status": "error"}) if item.id in failed else item
                    for item in generators
                ]
        if self._pending:
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

    def check(self, *, entities: Collection[str] | None = None) -> EngineReport:
        report = self.build(incremental=False, entities=entities)
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

    def _output_scope_errors(self) -> list[Diagnostic]:
        errors: list[Diagnostic] = []
        for generator_config in self._enabled_generators():
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                continue
            if getattr(type(plugin), "output_scope", "model") != "entity":
                errors.append(
                    error(
                        "EG303",
                        f"generator {generator_config.id} does not support per-entity output",
                        path=generator_config.id,
                    )
                )
        return errors

    def _enabled_generators(self) -> list[GeneratorConfig]:
        return [
            item for item in self.rules.generators if item.enabled or self.config.include_disabled
        ]

    def _input_fingerprint(
        self,
        sources: list[Path],
        resources: dict[str, ImportedFile],
    ) -> str | None:
        if self.config.allow_outside_imports:
            self._disable_incremental("allow_outside_imports is enabled")
            return None
        if self.rules.diagnostics.stale_dates:
            self._disable_incremental("diagnostics.stale_dates is enabled")
            return None
        if self.config.force or self.config.clean:
            self._disable_incremental("force or clean is enabled")
            return None
        if not self._enabled_generators():
            self._disable_incremental("no enabled generators")
            return None

        resolved_sources = [path.resolve() for path in sources]
        if any(not path.is_relative_to(self.config_dir) for path in resolved_sources):
            self._disable_incremental("a source path is outside the project root")
            return None

        digest = hashlib.sha256()
        _digest_text(digest, __version__)
        _digest_text(
            digest,
            json.dumps(
                self.rules.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        _digest_text(digest, json.dumps(self.variables, ensure_ascii=False, sort_keys=True))
        for info in self.registry.list():
            _digest_text(digest, info.name)
            _digest_text(digest, "\0".join(info.versions))
            _digest_text(digest, "\0".join(sorted(info.primitive_types)))
            _digest_text(digest, info.extends or "")
            _digest_text(digest, json.dumps(info.base_versions, sort_keys=True))
            _digest_text(digest, info.api_version)
            _digest_text(digest, info.plugin_version)

        files = self._fingerprint_files(resolved_sources)
        if files is None:
            return None

        for path in sorted(files, key=lambda item: item.as_posix()):
            _digest_text(digest, path.relative_to(self.config_dir).as_posix())
            _digest_bytes(digest, files[path])
        for alias, resource in sorted(resources.items()):
            _digest_text(digest, alias)
            _digest_bytes(digest, resource.content)

        for generator_config in self._enabled_generators():
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                self._disable_incremental(f"generator plugin is not loaded: {generator_config.id}")
                return None
            _digest_text(digest, generator_config.id)
            _digest_text(digest, _plugin_version(plugin))
            _digest_text(digest, str(plugin.api_version))
            _digest_text(digest, str(getattr(type(plugin), "output_scope", "model")))
            _digest_text(digest, json.dumps(_input_formats(plugin), sort_keys=True))
        return digest.hexdigest()

    def _fingerprint_files(self, sources: list[Path]) -> dict[Path, bytes] | None:
        """Collect source documents and their input closure, or disable the cache."""
        files: dict[Path, bytes] = {}
        for source in sources:
            content = _read_file(source)
            if content is None:
                self._disable_incremental(f"cannot read source: {source}")
                return None
            files[source] = content

        pending = list(files)
        while pending:
            path = pending.pop()
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            data = self._parse_fingerprint_document(path, files[path])
            if data is None:
                return None
            format_name = data.get("format")
            if not isinstance(format_name, str) or not format_name:
                continue
            try:
                plugin = self.registry.get(format_name)
            except ConfigValidationError:
                self._disable_incremental(f"unknown or invalid format: {format_name}")
                return None
            try:
                inputs = plugin.input_paths(data, path.parent)
            except DocumentError as exc:
                self._disable_incremental(
                    f"format {format_name} cannot resolve inputs: {exc.message}"
                )
                return None
            if inputs is None:
                self._disable_incremental(
                    f"format {format_name} does not declare input dependencies"
                )
                return None
            for raw_path in inputs:
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    candidate = path.parent / candidate
                candidate = candidate.resolve()
                if not candidate.is_relative_to(self.config_dir) or not candidate.is_file():
                    self._disable_incremental(f"unsafe input path: {raw_path}")
                    return None
                if candidate in files:
                    continue
                content = _read_file(candidate)
                if content is None:
                    self._disable_incremental(f"cannot read input: {candidate}")
                    return None
                files[candidate] = content
                pending.append(candidate)
        return files

    def _parse_fingerprint_document(self, path: Path, content: bytes) -> dict[str, Any] | None:
        try:
            return parse_yaml(content.decode("utf-8"))
        except (UnicodeDecodeError, YamlLoadError) as exc:
            self._disable_incremental(f"invalid YAML: {path}: {exc}")
            return None

    def _disable_incremental(self, reason: str) -> None:
        self._incremental_reason = reason
        return None

    def _cached_report(
        self,
        fingerprint: str,
        started: float,
        discovery: list[Diagnostic],
    ) -> EngineReport | None:
        try:
            manifest = self.writer.load_manifest()
        except ManifestError:
            self._disable_incremental("manifest is missing or corrupt")
            return None
        diagnostics = self._filter_ignored(list(discovery))
        if _has_errors(diagnostics):
            self._disable_incremental("discovery diagnostics contain errors")
            return None
        enabled = self._enabled_generators()
        if not enabled:
            self._disable_incremental("no enabled generators")
            return None
        locations = {location.key: location for location in manifest.locations}
        expected = {self.writer.location_key(item.id, self._output_dir(item)) for item in enabled}
        if set(locations) != expected:
            extra = sorted(key.generator for key in set(locations) - expected)
            missing = sorted(key.generator for key in expected - set(locations))
            self._disable_incremental(
                f"manifest locations do not match enabled generators"
                f" (extra={extra}, missing={missing})"
            )
            return None

        generators: list[GeneratorReport] = []
        artifacts: list[ArtifactReport] = []
        for generator_config in enabled:
            plugin = self.generators.get(generator_config.id)
            if plugin is None:
                self._disable_incremental(f"generator plugin is not loaded: {generator_config.id}")
                return None
            key = self.writer.location_key(generator_config.id, self._output_dir(generator_config))
            location = locations[key]
            if (
                location.input_fingerprint != fingerprint
                or location.eggpipe_version != __version__
                or location.plugin_version != _plugin_version(plugin)
            ):
                self._disable_incremental(
                    f"input fingerprint or versions changed for {generator_config.id}"
                )
                return None
            output_dir = self._output_dir(generator_config)
            output_root = output_dir.resolve()
            for item in location.artifacts:
                target = (output_dir / item.path).resolve()
                if not target.is_relative_to(output_root):
                    self._disable_incremental(f"artifact path escapes output dir: {item.path}")
                    return None
                content = _read_file(target)
                if content is None:
                    self._disable_incremental(f"cannot read artifact: {item.path}")
                    return None
                if hashlib.sha256(content).hexdigest() != item.sha256:
                    self._disable_incremental(f"artifact is missing or changed: {item.path}")
                    return None
                artifacts.append(
                    ArtifactReport(
                        generator=generator_config.id,
                        path=item.path,
                        action="skip",
                        sha256=item.sha256,
                    )
                )
            generators.append(
                GeneratorReport(
                    id=generator_config.id,
                    name=plugin.name or generator_config.id,
                    status="skipped",
                    input_formats=_input_formats(plugin),
                    formats=[
                        FormatReport(name=item.name, version=item.version)
                        for item in location.formats
                    ],
                    duration_ms=0,
                )
            )

        # Без парсинга модели глобальная сводка форматов недоступна: не подменяем её нулями.
        self._formats = []
        self._pending = []
        self._timings = {
            "discovery_ms": self._timings.get("discovery_ms", 0),
            "fingerprint_ms": self._timings.get("fingerprint_ms", 0),
            "parse_ms": 0,
            "validate_ms": 0,
            "generate_ms": 0,
            "write_ms": 0,
        }
        return self._report(True, 0, diagnostics, generators, started, artifacts)

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
            raise ConfigValidationError(".eggpipe.yaml has no sources")
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
        selection = generator_config.input
        empty_slice = False
        if self._entities is not None:
            selected = set(self._entities)
            if selection.entities:
                overlap = tuple(name for name in selection.entities if name in selected)
                if overlap:
                    selection = selection.model_copy(update={"entities": overlap})
                else:
                    empty_slice = True
            else:
                selection = selection.model_copy(update={"entities": self._entities})
        if empty_slice:
            slice_ = ModelSlice()
            slice_diagnostics: list[Diagnostic] = []
        else:
            slice_, slice_diagnostics = select_slice(composition.model, selection)
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
                            "EG300",
                            f"validate_config {generator_config.id} failed: "
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
                            "EG300",
                            f"generator {generator_config.id} failed: {type(exc).__name__}: {exc}",
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
                    errors=[error("EG052", str(exc))],
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
        "fingerprint_ms": 0,
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
                        "EG014",
                        f"updated_at {updated.isoformat()} is older than "
                        f"mtime {file_date.isoformat()}",
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
        if entity.format is None or entity.format_version is None:
            continue
        key = (entity.format, entity.format_version)
        counts[key] = counts.get(key, 0) + 1
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


def _digest_text(digest: Any, value: str) -> None:
    _digest_bytes(digest, value.encode("utf-8"))


def _digest_bytes(digest: Any, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _read_file(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _stale_diagnostics(stale: list[StaleLocation]) -> list[Diagnostic]:
    return [
        warning(
            "EG051",
            "stale generated location in the manifest",
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
                        "EG042",
                        f"path {item.path} is already claimed by location "
                        f"{owner.generator}:{owner.output_dir}",
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
        return [error("EG301", f"generator {generator_id}: input_formats is required")]
    if accepted is not None and not isinstance(accepted, set):
        return [error("EG301", f"generator {generator_id}: input_formats must be set[str]")]
    errors: list[Diagnostic] = []
    for entity in slice_.entities:
        if entity.format is None:
            continue
        if not registry.accepts(entity.format, accepted):
            errors.append(
                error(
                    "EG033",
                    f"generator {generator_id} does not support format {entity.format}",
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
    return 2 if any(item.code in {"EG033", "EG303"} for item in diagnostics) else 1


__all__ = ["Engine"]
