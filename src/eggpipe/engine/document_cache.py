"""Persistent content-addressed document cache (L2, ADR-0020)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eggpipe.config.logging import get_logger
from eggpipe.core.cache import CACHE_VERSION, digest, dump_payload, restore_document
from eggpipe.core.document import ModelDocument
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.utils.exceptions import ConfigValidationError

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
        self._staged: dict[str, dict[str, Any]] = {}
        self._touched: set[str] = set()

    def read(self, path: Path) -> bytes | None:
        """Read a file once per run; ``None`` marks an unreadable path."""
        resolved = path.resolve()
        if resolved not in self._contents:
            try:
                self._contents[resolved] = resolved.read_bytes()
            except OSError:
                self._contents[resolved] = None
        return self._contents[resolved]

    def digest(self, path: Path) -> str | None:
        content = self.read(path)
        return None if content is None else digest(content)

    def entry(self, path: Path) -> CacheEntry | None:
        """Return a valid entry for the current file content, or ``None``."""
        key = self.digest(path)
        if key is None:
            return None
        self._touched.add(key)
        entry = self._meta_state().entries.get(key)
        if entry is None or not self._versions_match(entry):
            return None
        if not self._closure_matches(entry):
            return None
        return entry

    def load(self, path: Path) -> ModelDocument | None:
        """Load a cached document; any problem is a miss."""
        key = self.digest(path)
        if key is None or self.entry(path) is None:
            return None
        payload = self._read_payload(key)
        if payload is None:
            return None
        try:
            return restore_document(payload, path)
        except ValidationError as exc:
            _LOG.debug("document cache payload is invalid for %s: %s", path, exc)
            return None

    def remember(self, path: Path, document: ModelDocument) -> None:
        """Stage a successfully parsed document for persistence."""
        key = self.digest(path)
        if key is None:
            return
        entry = self._entry_for(path, document)
        if entry is None:
            return
        payload = dump_payload(document)
        try:
            restore_document(payload, path)
        except ValidationError as exc:
            _LOG.debug("document cache payload is not serializable for %s: %s", path, exc)
            return
        meta = self._meta_state()
        self._meta = meta.model_copy(update={"entries": {**meta.entries, key: entry}})
        self._staged[key] = payload
        self._touched.add(key)

    def persist(self) -> None:
        """Write staged payloads and prune entries not touched by this run."""
        meta = self._meta_state()
        entries = {key: value for key, value in meta.entries.items() if key in self._touched}
        if not self._staged and set(entries) == set(meta.entries):
            return
        try:
            self.docs_dir.mkdir(parents=True, exist_ok=True)
            for key, payload in self._staged.items():
                _write_json_atomic(self.docs_dir / f"{key}.json", payload)
            self._staged.clear()
            _write_json_atomic(
                self.meta_path,
                CacheMeta(
                    cache_version=CACHE_VERSION,
                    eggpipe_version=self.eggpipe_version,
                    entries=entries,
                ).model_dump(mode="json"),
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
        except (OSError, ValueError) as exc:
            _LOG.debug("document cache is ignored: %s", exc)
            self._meta = empty
            return empty
        if meta.cache_version != CACHE_VERSION or meta.eggpipe_version != self.eggpipe_version:
            _LOG.debug("document cache version mismatch")
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
            candidate = self.config_dir / relative
            if not candidate.is_relative_to(self.config_dir):
                return False
            content = self.read(candidate)
            if content is None or digest(content) != expected:
                return False
        return True

    def _entry_for(self, path: Path, document: ModelDocument) -> CacheEntry | None:
        try:
            plugin = self.registry.get(document.format)
        except ConfigValidationError:
            return None
        inputs: dict[str, str] = {}
        for spec in document.imports:
            candidate = (path.parent / spec.path).resolve()
            if not candidate.is_relative_to(self.config_dir):
                return None
            content = self.read(candidate)
            if content is None:
                return None
            inputs[candidate.relative_to(self.config_dir).as_posix()] = digest(content)
        return CacheEntry(
            format=document.format,
            format_version=document.version,
            format_plugin_version=str(getattr(plugin, "__version__", "unknown")),
            format_api_version=str(plugin.api_version),
            inputs=inputs,
        )

    def _read_payload(self, key: str) -> dict[str, Any] | None:
        try:
            data = json.loads((self.docs_dir / f"{key}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _prune_docs(self, entries: dict[str, CacheEntry]) -> None:
        for item in self.docs_dir.glob("*.json"):
            if item.stem not in entries:
                item.unlink(missing_ok=True)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = ["CacheEntry", "CacheMeta", "DocumentCache"]
