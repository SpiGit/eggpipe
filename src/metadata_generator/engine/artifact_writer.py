"""Планирование и запись артефактов с ownership и manifest."""

from __future__ import annotations

import hashlib
import json
import os
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

from metadata_generator.interfaces.diagnostics import Diagnostic, error, warning
from metadata_generator.interfaces.generator import Artifact
from metadata_generator.utils.exceptions import (
    ArtifactPathError,
    LockError,
    ManifestError,
)

WIN_RESERVED = {
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "CON",
    "PRN",
    "AUX",
    "NUL",
}


class ManifestArtifact(BaseModel):
    path: str
    sha256: str
    skipped: bool = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class Manifest(BaseModel):
    manifest_version: int = 1
    generator: str
    mg_version: str
    plugin_version: str
    format: dict[str, str]
    generated_at: datetime
    artifacts: list[ManifestArtifact] = Field(default_factory=list)

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

    @property
    def has_errors(self) -> bool:
        return any(item.level == "error" for item in self.diagnostics)


class ArtifactWriter:
    def __init__(self, *, mg_version: str) -> None:
        self.mg_version = mg_version

    def plan(
        self,
        *,
        generator_id: str,
        output_dir: Path,
        artifacts: list[Artifact],
        on_conflict: Literal["overwrite", "skip", "error"] = "overwrite",
        force: bool = False,
    ) -> ExecutionPlan:
        plan = ExecutionPlan()
        manifest = self.load_manifest(output_dir, generator_id)
        owned = {item.path for item in manifest.artifacts}
        seen: dict[str, str] = {}
        output_resolved = output_dir.resolve()

        for artifact in artifacts:
            try:
                target = validate_artifact_path(output_dir, artifact)
            except ArtifactPathError as exc:
                plan.diagnostics.append(error("MG040", str(exc), path=artifact.path))
                continue
            normalized = target.relative_to(output_resolved).as_posix()
            collision = seen.get(normalized.casefold())
            if collision is not None:
                plan.diagnostics.append(
                    error(
                        "MG042",
                        f"дубликат artifact path: {collision} и {normalized}",
                        path=normalized,
                    )
                )
                continue
            seen[normalized.casefold()] = normalized
            digest = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()
            exists = target.exists()
            if target.is_dir():
                plan.diagnostics.append(
                    error("MG041", "artifact path указывает на каталог", path=normalized)
                )
                continue

            if not exists:
                plan.artifacts.append(
                    PlannedArtifact(
                        generator_id=generator_id,
                        path=PurePosixPath(normalized),
                        target=target,
                        action="create",
                        sha256=digest,
                        content=artifact.content,
                    )
                )
                continue

            is_owned = normalized in owned
            if is_owned:
                if on_conflict == "skip":
                    plan.artifacts.append(
                        PlannedArtifact(
                            generator_id=generator_id,
                            path=PurePosixPath(normalized),
                            target=target,
                            action="skip",
                            sha256=digest,
                            content=artifact.content,
                            skipped=True,
                        )
                    )
                else:
                    plan.artifacts.append(
                        PlannedArtifact(
                            generator_id=generator_id,
                            path=PurePosixPath(normalized),
                            target=target,
                            action="update",
                            sha256=digest,
                            content=artifact.content,
                        )
                    )
                continue

            if on_conflict == "skip":
                plan.diagnostics.append(
                    warning(
                        "MG043",
                        "не-owned файл не перезаписан и не добавлен в manifest",
                        path=normalized,
                    )
                )
                continue
            if on_conflict == "error" or not force:
                plan.diagnostics.append(
                    error(
                        "MG041",
                        "файл не принадлежит генератору; перезапись только с --force",
                        path=normalized,
                    )
                )
                continue
            plan.artifacts.append(
                PlannedArtifact(
                    generator_id=generator_id,
                    path=PurePosixPath(normalized),
                    target=target,
                    action="update",
                    sha256=digest,
                    content=artifact.content,
                )
            )
        return plan

    def write(
        self,
        *,
        generator_id: str,
        output_dir: Path,
        plan: ExecutionPlan,
        plugin_version: str,
        format_name: str,
        format_version: str,
        cleanup: Literal["off", "prompt", "enabled"] = "off",
    ) -> list[Diagnostic]:
        if plan.has_errors:
            raise ManifestError("нельзя записывать план с ошибками")
        output_dir.mkdir(parents=True, exist_ok=True)
        mg_dir = output_dir / ".mg"
        manifests_dir = mg_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        staging = output_dir / f".mg-staging-{os.getpid()}-{uuid.uuid4().hex}"
        staging.mkdir()
        diagnostics: list[Diagnostic] = []
        try:
            for item in plan.artifacts:
                if item.action == "skip":
                    continue
                source = staging / item.path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(item.content, encoding="utf-8", newline="\n")
                item.target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, item.target)

            entries: list[ManifestArtifact] = []
            for item in plan.artifacts:
                if item.action == "skip":
                    current = item.target.exists()
                    digest = _sha256_file(item.target) if current else item.sha256
                    entries.append(
                        ManifestArtifact(path=str(item.path), sha256=digest, skipped=True)
                    )
                else:
                    entries.append(
                        ManifestArtifact(
                            path=str(item.path),
                            sha256=item.sha256,
                            skipped=False,
                        )
                    )
            current_paths = {str(item.path) for item in plan.artifacts}
            old = self.load_manifest(output_dir, generator_id)
            for item in old.artifacts:
                if item.path in current_paths or item.skipped:
                    if item.path not in current_paths:
                        entries.append(item)
                    continue
                target = output_dir / item.path
                if not target.exists():
                    continue
                if _sha256_file(target) != item.sha256:
                    diagnostics.append(
                        warning(
                            "MG050",
                            "изменённый owned-файл не удалён при cleanup",
                            path=item.path,
                        )
                    )
                    entries.append(item)
                    continue
                if cleanup == "enabled":
                    target.unlink()
                else:
                    entries.append(item)
            manifest = Manifest(
                generator=generator_id,
                mg_version=self.mg_version,
                plugin_version=plugin_version,
                format={"name": format_name, "version": format_version},
                generated_at=datetime.now(UTC),
                artifacts=entries,
            )
            _write_json_atomic(manifests_dir / f"{generator_id}.json", manifest)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return diagnostics

    def check(
        self,
        *,
        output_dir: Path,
        plan: ExecutionPlan,
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for item in plan.artifacts:
            if item.action == "skip":
                continue
            if not item.target.exists():
                diagnostics.append(
                    error("MG300", "ожидаемый артефакт отсутствует", path=str(item.path))
                )
                continue
            actual = _sha256_file(item.target)
            if actual != item.sha256:
                diagnostics.append(error("MG300", "артефакт устарел (drift)", path=str(item.path)))
        return diagnostics

    def clean_manifest(
        self,
        *,
        output_dir: Path,
        generator_id: str,
        dry_run: bool = False,
    ) -> list[Diagnostic]:
        manifest_path = output_dir / ".mg" / "manifests" / f"{generator_id}.json"
        if not manifest_path.is_file():
            return []
        manifest = self.load_manifest(output_dir, generator_id)
        kept: list[ManifestArtifact] = []
        diagnostics: list[Diagnostic] = []
        for item in manifest.artifacts:
            if item.skipped:
                kept.append(item)
                continue
            target = output_dir / item.path
            if not target.exists():
                continue
            if _sha256_file(target) != item.sha256:
                diagnostics.append(
                    warning(
                        "MG050",
                        "изменённый owned-файл не удалён при cleanup",
                        path=item.path,
                    )
                )
                kept.append(item)
                continue
            if dry_run:
                kept.append(item)
                continue
            target.unlink()
        if not dry_run:
            updated = manifest.model_copy(
                update={
                    "generated_at": datetime.now(UTC),
                    "artifacts": kept,
                }
            )
            manifests_dir = output_dir / ".mg" / "manifests"
            _write_json_atomic(manifests_dir / f"{generator_id}.json", updated)
        return diagnostics

    def load_manifest(self, output_dir: Path, generator_id: str) -> Manifest:
        path = output_dir / ".mg" / "manifests" / f"{generator_id}.json"
        if not path.is_file():
            return Manifest(
                generator=generator_id,
                mg_version=self.mg_version,
                plugin_version="",
                format={},
                generated_at=datetime.now(UTC),
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Manifest.model_validate(data)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ManifestError(f"не удалось прочитать manifest {path}: {exc}") from exc

    @contextmanager
    def write_lock(self, output_dir: Path) -> Generator[None, None, None]:
        mg_dir = output_dir / ".mg"
        mg_dir.mkdir(parents=True, exist_ok=True)
        lock = mg_dir / "lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise LockError(f"output_dir уже используется: {lock}") from exc
        try:
            os.write(descriptor, f"{os.getpid()}\n".encode())
            yield
        finally:
            os.close(descriptor)
            lock.unlink(missing_ok=True)


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
            or part.startswith(".mg")
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


__all__ = [
    "ArtifactWriter",
    "ExecutionPlan",
    "Manifest",
    "ManifestArtifact",
    "PlannedArtifact",
    "validate_artifact_path",
]
