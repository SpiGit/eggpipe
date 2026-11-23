"""Path-free document payload for the L2 parse cache (ADR-0020)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import SourceModel

CACHE_VERSION = 1


class CachedFormatProbe(Protocol):
    """What discovery needs from the internal document cache."""

    def entry(self, path: Path) -> object | None: ...


def digest(content: bytes) -> str:
    """Return the cache key for raw document bytes."""
    return hashlib.sha256(content).hexdigest()


def dump_payload(document: ModelDocument) -> dict[str, Any]:
    """Serialize a document without path-dependent fields."""
    return document.model_dump(mode="json", exclude={"path"})


def restore_document(payload: dict[str, Any], path: Path) -> ModelDocument:
    """Rebuild a document from a cached payload and attach path-dependent fields."""
    data = dict(payload)
    data["path"] = str(path)
    document = ModelDocument.model_validate(data)
    entities = tuple(
        entity.model_copy(
            update={
                "source": path,
                "format": document.format,
                "format_version": document.version,
                "fields": tuple(
                    field.model_copy(update={"source": path}) for field in entity.fields
                ),
            }
        )
        for entity in document.model.entities
    )
    model = SourceModel(
        name=document.model.name,
        description=document.model.description,
        metadata=document.model.metadata,
        entities=entities,
        enums=document.model.enums,
        types=document.model.types,
    )
    return document.model_copy(update={"path": path, "model": model})


__all__ = ["CACHE_VERSION", "CachedFormatProbe", "digest", "dump_payload", "restore_document"]
