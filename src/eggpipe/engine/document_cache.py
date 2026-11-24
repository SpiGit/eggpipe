"""Persistent content-addressed document cache (L2, ADR-0020)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eggpipe.config.logging import get_logger
from eggpipe.core.cache import CACHE_VERSION, digest, dump_payload, restore_document
from eggpipe.core.document import ModelDocument
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.engine.report import CacheMissReasons, CacheReport
from eggpipe.interfaces.formats import FormatPlugin
from eggpipe.utils.exceptions import ConfigValidationError, DocumentError
from eggpipe.utils.files import write_json_atomic
from eggpipe.utils.yaml import YamlLoadError, parse_yaml

_LOG = get_logger(__name__)
META_FILE = "meta.json"
DOCS_DIR = "docs"


class CacheEntry(BaseModel):
    """Per-document metadata stored in ``meta.json``."""

    format: str
    format_version: str
    format_plugin_version: str
    format_api_version: str
    inputs: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CacheMeta(BaseModel):
    """Content-addressed document cache index."""

    cache_version: int = CACHE_VERSION
    eggpipe_version: str
    entries: dict[str, CacheEntry] = Field(default_factory=dict)
    paths: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentCache:
    """Internal parse cache; corrupt entries are misses, never errors."""

    def __init__(
        self,
        *,
        config_dir: Path,
        registry: FormatRegistry,
        eggpipe_version: str,
    ) -> None:
        self.config_dir = config_dir
        self.registry = registry
        self.eggpipe_version = eggpipe_version
        self.root = config_dir / ".eggpipe" / "cache"
        self.meta_path = self.root / META_FILE
        self.docs_dir = self.root / DOCS_DIR
        self._meta: CacheMeta | None = None
        self._contents: dict[Path, bytes | None] = {}
        self._digests: dict[Path, str | None] = {}
        self._staged: dict[str, dict[str, Any]] = {}
        self._touched: set[str] = set()
        self._invalid: set[str] = set()
        self._meta_invalid = False
        self._meta_version_mismatch = False
        self.hits = 0
        self.misses = 0
        self.miss_reasons: dict[str, int] = {
            "changed": 0,
            "missing": 0,
            "invalid": 0,
            "version": 0,
        }

    def read(self, path: Path) -> bytes | None:
        """Read a file once per run; ``None`` marks an unreadable path.

        The memo lives as long as this instance, i.e. one Engine run.
        """
        resolved = path.resolve()
        if resolved not in self._contents:
            try:
                self._contents[resolved] = resolved.read_bytes()
            except OSError:
                self._contents[resolved] = None
        return self._contents[resolved]

    def digest(self, path: Path) -> str | None:
        resolved = path.resolve()
        if resolved not in self._digests:
            content = self.read(resolved)
            self._digests[resolved] = None if content is None else digest(content)
        return self._digests[resolved]

    def entry(self, path: Path) -> CacheEntry | None:
        """Return a valid entry for the current file content, or ``None``."""
        entry, _ = self._lookup(path)
        return entry

    def load(self, path: Path) -> ModelDocument | None:
        """Load a cached document; any problem is a miss."""
        key = self.digest(path)
        if key is None:
            return None
        entry, reason = self._lookup(path)
        if entry is None:
            self._record_miss(reason or "missing")
            return None
        payload = self._read_payload(key)
        if payload is None:
            payload_file = self.docs_dir / f"{key}.json"
            self._record_miss("invalid" if payload_file.exists() else "missing")
            return None
        try:
            document = restore_document(payload, path)
        except (ValidationError, ValueError, TypeError, ArithmeticError, RecursionError) as exc:
            _LOG.debug("document cache payload is invalid for %s: %s", path, exc)
            self._record_miss("invalid")
            return None
        self.hits += 1
        return document

    def _lookup(self, path: Path) -> tuple[CacheEntry | None, str]:
        key = self.digest(path)
        if key is None:
            return None, ""
        entry = self._meta_state().entries.get(key)
        if entry is None:
            return None, self._absent_reason(path)
        if not self._versions_match(entry) or not self._closure_matches(entry):
            self._invalid.add(key)
            return None, "version"
        self._touched.add(key)
        self._remember_path(path, key)
        return entry, ""

    def _absent_reason(self, path: Path) -> str:
        if self._meta_invalid:
            return "invalid"
        if self._meta_version_mismatch:
            return "version"
        relative = self._relative(path)
        if relative is not None and relative in self._meta_state().paths:
            return "changed"
        return "missing"

    def _relative(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self.config_dir.resolve()).as_posix()
        except ValueError:
            return None

    def _remember_path(self, path: Path, key: str) -> None:
        relative = self._relative(path)
        if relative is None:
            return
        meta = self._meta_state()
        if meta.paths.get(relative) == key:
            return
        self._meta = meta.model_copy(update={"paths": {**meta.paths, relative: key}})

    def _record_miss(self, reason: str) -> None:
        self.misses += 1
        self.miss_reasons[reason] = self.miss_reasons.get(reason, 0) + 1

    def report(self) -> CacheReport:
        """Snapshot metrics for the current run (ADR-0021)."""
        entries, size = self._disk_usage()
        return CacheReport(
            hits=self.hits,
            misses=self.misses,
            miss_reasons=CacheMissReasons(**self.miss_reasons),
            entries=entries,
            bytes=size,
        )

    def _disk_usage(self) -> tuple[int, int]:
        entries = 0
        size = 0
        try:
            for item in self.docs_dir.glob("*.json"):
                try:
                    size += item.stat().st_size
                except OSError:
                    continue
                entries += 1
        except OSError:
            return 0, 0
        return entries, size

    def remember(self, path: Path, document: ModelDocument) -> None:
        """Stage a successfully parsed document for persistence."""
        try:
            key = self.digest(path)
            if key is None:
                return
            entry = self._entry_for(path, document)
            if entry is None:
                return
            payload = dump_payload(document)
            restore_document(payload, path)
        except (TypeError, ValueError, ArithmeticError) as exc:
            _LOG.debug("document cache payload is not serializable for %s: %s", path, exc)
            return
        meta = self._meta_state()
        paths = dict(meta.paths)
        relative = self._relative(path)
        if relative is not None:
            paths[relative] = key
        self._meta = meta.model_copy(
            update={"entries": {**meta.entries, key: entry}, "paths": paths}
        )
        self._staged[key] = payload
        self._touched.add(key)
        self._invalid.discard(key)

    def persist(self) -> None:
        """Write staged payloads and prune entries not touched by this run."""
        meta = self._meta_state()
        entries = {
            key: value
            for key, value in meta.entries.items()
            if key in self._touched and key not in self._invalid
        }
        paths = {path: key for path, key in meta.paths.items() if key in entries}
        if not self._staged and entries == meta.entries and paths == meta.paths:
            return
        try:
            self.docs_dir.mkdir(parents=True, exist_ok=True)
            for key, payload in self._staged.items():
                write_json_atomic(
                    self.docs_dir / f"{key}.json", payload, compact=True, durable=False
                )
            self._staged.clear()
            write_json_atomic(
                self.meta_path,
                CacheMeta(
                    cache_version=CACHE_VERSION,
                    eggpipe_version=self.eggpipe_version,
                    entries=entries,
                    paths=paths,
                ),
                compact=True,
                durable=False,
            )
            self._prune_docs(entries)
        except OSError as exc:
            _LOG.debug("document cache was not persisted: %s", exc)

    def _meta_state(self) -> CacheMeta:
        if self._meta is not None:
            return self._meta
        empty = CacheMeta(cache_version=CACHE_VERSION, eggpipe_version=self.eggpipe_version)
        try:
            data = json.loads(self.meta_path.read_text(encoding="utf-8"))
            meta = CacheMeta.model_validate(data)
        except FileNotFoundError:
            self._meta = empty
            return empty
        except (OSError, ValueError, RecursionError) as exc:
            _LOG.debug("document cache is ignored: %s", exc)
            self._meta_invalid = True
            self._meta = empty
            return empty
        if meta.cache_version != CACHE_VERSION or meta.eggpipe_version != self.eggpipe_version:
            _LOG.debug("document cache version mismatch")
            self._meta_version_mismatch = True
            self._meta = empty
            return empty
        self._meta = meta
        return meta

    def _versions_match(self, entry: CacheEntry) -> bool:
        try:
            plugin = self.registry.get(entry.format)
        except ConfigValidationError:
            return False
        return (
            entry.format_version in plugin.supported_versions
            and entry.format_plugin_version == str(getattr(plugin, "__version__", "unknown"))
            and entry.format_api_version == str(plugin.api_version)
        )

    def _closure_matches(self, entry: CacheEntry) -> bool:
        for relative, expected in entry.inputs.items():
            candidate = (self.config_dir / relative).resolve()
            if not candidate.is_relative_to(self.config_dir.resolve()):
                return False
            if self.digest(candidate) != expected:
                return False
        return True

    def _entry_for(self, path: Path, document: ModelDocument) -> CacheEntry | None:
        try:
            plugin = self.registry.get(document.format)
        except ConfigValidationError:
            return None
        inputs = self._declared_inputs(path, plugin)
        if inputs is None:
            return None
        return CacheEntry(
            format=document.format,
            format_version=document.version,
            format_plugin_version=str(getattr(plugin, "__version__", "unknown")),
            format_api_version=str(plugin.api_version),
            inputs=inputs,
        )

    def _declared_inputs(self, path: Path, plugin: FormatPlugin) -> dict[str, str] | None:
        content = self.read(path)
        if content is None:
            return None
        try:
            raw = parse_yaml(content.decode("utf-8"))
        except (UnicodeDecodeError, YamlLoadError):
            return None
        try:
            declared = plugin.input_paths(raw, path.parent)
        except DocumentError:
            return None
        if declared is None:
            return None
        inputs: dict[str, str] = {}
        for raw_path in declared:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            candidate = candidate.resolve()
            if not candidate.is_relative_to(self.config_dir.resolve()):
                return None
            value = self.digest(candidate)
            if value is None:
                return None
            inputs[candidate.relative_to(self.config_dir.resolve()).as_posix()] = value
        return inputs

    def _read_payload(self, key: str) -> dict[str, Any] | None:
        try:
            data = json.loads((self.docs_dir / f"{key}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            return None
        return data if isinstance(data, dict) else None

    def _prune_docs(self, entries: dict[str, CacheEntry]) -> None:
        for item in self.docs_dir.glob("*.json"):
            if item.stem not in entries:
                item.unlink(missing_ok=True)


__all__ = ["CacheEntry", "CacheMeta", "DocumentCache"]
