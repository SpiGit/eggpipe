"""Планирование и запись артефактов с глобальным manifest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eggpipe.core.model import FormatInfo
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning
from eggpipe.interfaces.generator import Artifact
from eggpipe.utils.exceptions import (
    ArtifactPathError,
    LockError,
    ManifestError,
)

MANIFEST_VERSION = 2
WIN_RESERVED = {
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "CON",
    "PRN",
    "AUX",
    "NUL",
}


@dataclass(frozen=True, order=True)
class LocationKey:
    generator: str
    output_dir: str


class ManifestFormat(BaseModel):
    name: str
    version: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestArtifact(BaseModel):
    path: str
    sha256: str
    skipped: bool = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestLocation(BaseModel):
    generator: str
    output_dir: str
    eggpipe_version: str
    plugin_version: str
    formats: list[ManifestFormat] = Field(default_factory=list)
    generated_at: datetime
    artifacts: list[ManifestArtifact] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def key(self) -> LocationKey:
        return LocationKey(self.generator, self.output_dir)


class Manifest(BaseModel):
    manifest_version: int
    locations: list[ManifestLocation] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class PlannedArtifact:
    generator_id: str
    path: PurePosixPath
    target: Path
    action: Literal["create", "update", "skip"]
    sha256: str
    content: str
    skipped: bool = False


@dataclass
class ExecutionPlan:
    artifacts: list[PlannedArtifact] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    formats: frozenset[FormatInfo] = frozenset()

    @property
    def has_errors(self) -> bool:
        return any(item.level == "error" for item in self.diagnostics)


@dataclass(frozen=True)
class CleanResult:
    removed_artifacts: int
    removed_locations: int
    diagnostics: list[Diagnostic]


@dataclass
class _PlanState:
    plan: ExecutionPlan
    generator_id: str
    output_resolved: Path
    ownership: dict[Path, LocationKey]
    current: LocationKey
    on_conflict: Literal["overwrite", "skip", "error"]
    force: bool
    seen: dict[str, str] = field(default_factory=dict)


class ArtifactWriter:
    def __init__(self, *, eggpipe_version: str, config_dir: Path) -> None:
        self.eggpipe_version = eggpipe_version
        self.config_dir = config_dir.resolve()
        self.state_dir = self.config_dir / ".eggpipe"
        self.manifest_path = self.state_dir / "manifest.json"

    def plan(
        self,
        *,
        generator_id: str,
        output_dir: Path,
        artifacts: list[Artifact],
        on_conflict: Literal["overwrite", "skip", "error"] = "overwrite",
        force: bool = False,
        formats: frozenset[FormatInfo] = frozenset(),
    ) -> ExecutionPlan:
        manifest = self.load_manifest()
        state = _PlanState(
            plan=ExecutionPlan(formats=formats),
            generator_id=generator_id,
            output_resolved=output_dir.resolve(),
            ownership=self._ownership(manifest),
            current=self.location_key(generator_id, output_dir),
            on_conflict=on_conflict,
            force=force,
        )
        for artifact in artifacts:
            planned = self._plan_artifact(state, artifact)
            if planned is not None:
                state.plan.artifacts.append(planned)
        return state.plan

    def _plan_artifact(
        self,
        state: _PlanState,
        artifact: Artifact,
    ) -> PlannedArtifact | None:
        try:
            target = validate_artifact_path(state.output_resolved, artifact)
        except ArtifactPathError as exc:
            state.plan.diagnostics.append(error("MG040", str(exc), path=artifact.path))
            return None
        normalized = target.relative_to(state.output_resolved).as_posix()
        collision = _collision(state.seen, normalized)
        if collision is not None:
            state.plan.diagnostics.append(
                error(
                    "MG042",
                    f"дубликат artifact path: {collision} и {normalized}",
                    path=normalized,
                )
            )
            return None
        state.seen[normalized.casefold()] = normalized
        if target.is_dir():
            state.plan.diagnostics.append(
                error("MG041", "artifact path указывает на каталог", path=normalized)
            )
            return None
        owner = state.ownership.get(target)
        if owner is not None and owner != state.current:
            state.plan.diagnostics.append(
                error(
                    "MG041",
                    f"файл принадлежит другому location: {owner.generator}:{owner.output_dir}",
                    path=normalized,
                )
            )
            return None
        prefix = _owned_prefix(target, state.ownership, state.current)
        if prefix is not None:
            state.plan.diagnostics.append(
                error("MG042", f"конфликт пути с другим location: {prefix}", path=normalized)
            )
            return None
        digest = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()
        if not target.exists():
            return self._planned(
                generator_id=state.generator_id,
                normalized=normalized,
                target=target,
                action="create",
                digest=digest,
                content=artifact.content,
            )
        return self._plan_existing(state, artifact, target, normalized, digest, owner)

    def _plan_existing(
        self,
        state: _PlanState,
        artifact: Artifact,
        target: Path,
        normalized: str,
        digest: str,
        owner: LocationKey | None,
    ) -> PlannedArtifact | None:
        if state.on_conflict == "error":
            state.plan.diagnostics.append(
                error("MG041", "on_conflict: error — файл уже существует", path=normalized)
            )
            return None
        if owner == state.current:
            skipped = state.on_conflict == "skip"
            return self._planned(
                generator_id=state.generator_id,
                normalized=normalized,
                target=target,
                action="skip" if skipped else "update",
                digest=digest,
                content=artifact.content,
                skipped=skipped,
            )
        if state.on_conflict == "skip":
            state.plan.diagnostics.append(
                warning(
                    "MG043",
                    "не-owned файл не перезаписан и не добавлен в manifest",
                    path=normalized,
                )
            )
            return None
        if not state.force:
            state.plan.diagnostics.append(
                error(
                    "MG041",
                    "файл не принадлежит генератору; перезапись только с --force",
                    path=normalized,
                )
            )
            return None
        return self._planned(
            generator_id=state.generator_id,
            normalized=normalized,
            target=target,
            action="update",
            digest=digest,
            content=artifact.content,
        )

    @staticmethod
    def _planned(
        *,
        generator_id: str,
        normalized: str,
        target: Path,
        action: Literal["create", "update", "skip"],
        digest: str,
        content: str,
        skipped: bool = False,
    ) -> PlannedArtifact:
        return PlannedArtifact(
            generator_id=generator_id,
            path=PurePosixPath(normalized),
            target=target,
            action=action,
            sha256=digest,
            content=content,
            skipped=skipped,
        )

    def write(
        self,
        *,
        generator_id: str,
        output_dir: Path,
        plan: ExecutionPlan,
        plugin_version: str,
        cleanup: Literal["off", "prompt", "enabled"] = "off",
    ) -> list[Diagnostic]:
        if plan.has_errors:
            raise ManifestError("нельзя записывать план с ошибками")
        diagnostics: list[Diagnostic] = []
        if plan.artifacts:
            output_dir.mkdir(parents=True, exist_ok=True)
            _sweep_staging(output_dir)
            _stage_artifacts(plan, output_dir)

        entries = self._current_entries(plan)
        current_paths = {str(item.path) for item in plan.artifacts}
        manifest = self.load_manifest()
        old = self._find_location(manifest, generator_id, output_dir)
        if old is not None:
            entries.extend(
                self._cleanup_location(
                    old,
                    output_dir,
                    current_paths,
                    cleanup,
                    diagnostics,
                )
            )
        location = ManifestLocation(
            generator=generator_id,
            output_dir=self._output_rel(output_dir),
            eggpipe_version=self.eggpipe_version,
            plugin_version=plugin_version,
            formats=_manifest_formats(plan.formats),
            generated_at=datetime.now(UTC),
            artifacts=entries,
        )
        key = self.location_key(generator_id, output_dir)
        locations = [self._prune_missing(item) for item in manifest.locations if item.key != key]
        if entries:
            locations.append(location)
        self.save_manifest(Manifest(manifest_version=MANIFEST_VERSION, locations=locations))
        return diagnostics

    def check(self, *, plan: ExecutionPlan) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for item in plan.artifacts:
            if item.action == "skip":
                continue
            if not item.target.exists():
                diagnostics.append(
                    error("MG300", "ожидаемый артефакт отсутствует", path=str(item.path))
                )
                continue
            if _sha256_file(item.target) != item.sha256:
                diagnostics.append(error("MG300", "артефакт устарел (drift)", path=str(item.path)))
        return diagnostics

    def clean(self, *, dry_run: bool = False) -> CleanResult:
        manifest = self.load_manifest()
        diagnostics: list[Diagnostic] = []
        removed_artifacts = 0
        kept_locations: list[ManifestLocation] = []
        for location in manifest.locations:
            output_dir = self._location_output(location)
            kept = self._cleanup_location(
                location,
                output_dir,
                current_paths=set(),
                cleanup="enabled",
                diagnostics=diagnostics,
                dry_run=dry_run,
            )
            removed_artifacts += len(location.artifacts) - len(kept)
            if kept:
                kept_locations.append(
                    location.model_copy(
                        update={
                            "generated_at": datetime.now(UTC),
                            "artifacts": kept,
                        }
                    )
                )
        removed_locations = len(manifest.locations) - len(kept_locations)
        if not dry_run:
            if kept_locations:
                self.save_manifest(
                    Manifest(manifest_version=MANIFEST_VERSION, locations=kept_locations)
                )
            else:
                self.manifest_path.unlink(missing_ok=True)
        return CleanResult(
            removed_artifacts=removed_artifacts,
            removed_locations=removed_locations,
            diagnostics=diagnostics,
        )

    def load_manifest(self) -> Manifest:
        if not self.manifest_path.is_file():
            return Manifest(manifest_version=MANIFEST_VERSION)
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest = Manifest.model_validate(data)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ManifestError(
                f"не удалось прочитать manifest {self.manifest_path}: {exc}"
            ) from exc
        if manifest.manifest_version != MANIFEST_VERSION:
            raise ManifestError(f"manifest_version {manifest.manifest_version} не поддерживается")
        return manifest

    def save_manifest(self, manifest: Manifest) -> None:
        _write_json_atomic(self.manifest_path, manifest)

    def location_key(self, generator_id: str, output_dir: Path) -> LocationKey:
        return LocationKey(generator_id, self._output_rel(output_dir))

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        lock = self.state_dir / "lock"
        descriptor = _acquire_lock(lock)
        try:
            os.write(descriptor, f"{os.getpid()}\n".encode())
            yield
        finally:
            os.close(descriptor)
            lock.unlink(missing_ok=True)

    def _current_entries(self, plan: ExecutionPlan) -> list[ManifestArtifact]:
        entries: list[ManifestArtifact] = []
        for item in plan.artifacts:
            if item.action == "skip":
                digest = _sha256_file(item.target) if item.target.exists() else item.sha256
                entries.append(ManifestArtifact(path=str(item.path), sha256=digest, skipped=True))
            else:
                entries.append(
                    ManifestArtifact(path=str(item.path), sha256=item.sha256, skipped=False)
                )
        return entries

    def _cleanup_location(
        self,
        location: ManifestLocation,
        output_dir: Path,
        current_paths: set[str],
        cleanup: Literal["off", "prompt", "enabled"],
        diagnostics: list[Diagnostic],
        *,
        dry_run: bool = False,
    ) -> list[ManifestArtifact]:
        kept: list[ManifestArtifact] = []
        for item in location.artifacts:
            if item.path in current_paths:
                continue
            if item.skipped:
                kept.append(item)
                continue
            target = output_dir / item.path
            if not target.exists():
                continue
            if _sha256_file(target) != item.sha256:
                diagnostics.append(
                    warning("MG050", "изменённый owned-файл не удалён при cleanup", path=item.path)
                )
                kept.append(item)
                continue
            if cleanup == "enabled":
                if not dry_run:
                    target.unlink()
            else:
                kept.append(item)
        return kept

    def _find_location(
        self,
        manifest: Manifest,
        generator_id: str,
        output_dir: Path,
    ) -> ManifestLocation | None:
        key = self.location_key(generator_id, output_dir)
        for location in manifest.locations:
            if location.key == key:
                return location
        return None

    def _prune_missing(self, location: ManifestLocation) -> ManifestLocation:
        output_dir = self._location_output(location)
        kept = [
            item for item in location.artifacts if item.skipped or (output_dir / item.path).exists()
        ]
        if len(kept) == len(location.artifacts):
            return location
        return location.model_copy(update={"artifacts": kept})

    def _ownership(self, manifest: Manifest) -> dict[Path, LocationKey]:
        result: dict[Path, LocationKey] = {}
        for location in manifest.locations:
            output_dir = self._location_output(location)
            for artifact in location.artifacts:
                target = (output_dir / artifact.path).resolve()
                if target.exists():
                    result[target] = location.key
        return result

    def _location_output(self, location: ManifestLocation) -> Path:
        path = Path(location.output_dir)
        return path if path.is_absolute() else (self.config_dir / path).resolve()

    def _output_rel(self, output_dir: Path) -> str:
        resolved = output_dir.resolve()
        try:
            return resolved.relative_to(self.config_dir).as_posix()
        except ValueError:
            return resolved.as_posix()


def _sweep_staging(output_dir: Path) -> None:
    for path in output_dir.glob(".eggpipe-staging-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def _acquire_lock(lock: Path) -> int:
    try:
        return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        if not _stale_lock(lock):
            pid = _lock_pid(lock)
            hint = f" (PID {pid})" if pid is not None else ""
            raise LockError(
                f"manifest уже используется: {lock}{hint}; "
                "если процесс не запущен, удалите lock вручную"
            ) from exc
        lock.unlink(missing_ok=True)
        try:
            return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as retry:
            raise LockError(f"manifest уже используется: {lock}") from retry


def _stale_lock(lock: Path) -> bool:
    pid = _lock_pid(lock)
    return pid is None or not _pid_alive(pid)


def _lock_pid(lock: Path) -> int | None:
    try:
        return int(lock.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _stage_artifacts(plan: ExecutionPlan, output_dir: Path) -> None:
    staging = output_dir / f".eggpipe-staging-{os.getpid()}-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        for item in plan.artifacts:
            if item.action == "skip":
                continue
            source = staging / item.path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(item.content, encoding="utf-8", newline="\n")
            item.target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, item.target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _collision(seen: dict[str, str], normalized: str) -> str | None:
    key = normalized.casefold()
    if key in seen:
        return seen[key]
    for other in seen:
        if key.startswith(f"{other}/") or other.startswith(f"{key}/"):
            return seen[other]
    return None


def _owned_prefix(
    target: Path,
    ownership: dict[Path, LocationKey],
    current: LocationKey,
) -> str | None:
    name = target.as_posix().casefold()
    for other, owner in ownership.items():
        if owner == current:
            continue
        other_name = other.as_posix().casefold()
        if name.startswith(f"{other_name}/") or other_name.startswith(f"{name}/"):
            return f"{owner.generator}:{owner.output_dir}"
    return None


def _manifest_formats(formats: frozenset[FormatInfo]) -> list[ManifestFormat]:
    return [
        ManifestFormat(name=item.name, version=item.version)
        for item in sorted(formats, key=lambda item: (item.name, item.version))
    ]


def validate_artifact_path(output_dir: Path, artifact: Artifact) -> Path:
    if not isinstance(artifact.content, str):
        raise ArtifactPathError("content должен быть строкой")
    if artifact.content.startswith("\ufeff"):
        raise ArtifactPathError("content не должен содержать BOM")
    if "\r" in artifact.content:
        raise ArtifactPathError("content должен использовать LF")

    raw = unicodedata.normalize("NFC", artifact.path)
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts:
        raise ArtifactPathError("path должен быть относительным")
    if len(raw) > 4096:
        raise ArtifactPathError("path слишком длинный")
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if (
            part in {"", ".", ".."}
            or re.match(r"^[A-Za-z]:", part)
            or part.startswith(".eggpipe")
            or stem in WIN_RESERVED
            or part.endswith((" ", "."))
            or "\x00" in part
            or "\\" in part
        ):
            raise ArtifactPathError(f"недопустимый сегмент пути: {part!r}")
        if len(part) > 255:
            raise ArtifactPathError("сегмент пути слишком длинный")

    output_resolved = output_dir.resolve()
    target = (output_resolved / path).resolve()
    if not target.is_relative_to(output_resolved):
        raise ArtifactPathError("path выходит за пределы output_dir")
    return target


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


__all__ = [
    "ArtifactWriter",
    "CleanResult",
    "ExecutionPlan",
    "LocationKey",
    "Manifest",
    "ManifestArtifact",
    "ManifestFormat",
    "ManifestLocation",
    "PlannedArtifact",
    "validate_artifact_path",
]
