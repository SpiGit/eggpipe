"""Path-free document payload for the L2 parse cache (ADR-0020)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import SourceModel

CACHE_VERSION = 1
_TAG = "__eggpipe_type__"


class CachedFormatProbe(Protocol):
    """What discovery needs from the internal document cache."""

    def entry(self, path: Path) -> object | None: ...


def digest(content: bytes) -> str:
    """Return the cache key for raw document bytes."""
    return hashlib.sha256(content).hexdigest()


def dump_payload(document: ModelDocument) -> dict[str, Any]:
    """Serialize a document without path-dependent fields, keeping scalar types."""
    return _encode(document.model_dump(mode="python", exclude={"path"}))


def restore_document(payload: dict[str, Any], path: Path) -> ModelDocument:
    """Rebuild a document from a cached payload and attach path-dependent fields."""
    data = _decode(payload)
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


def _encode(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, datetime):
        return {_TAG: "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {_TAG: "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {_TAG: "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {_TAG: "decimal", "value": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported cache value: {type(value).__name__}")


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get(_TAG)
    if tag is not None and set(value) == {_TAG, "value"}:
        raw = str(value["value"])
        if tag == "datetime":
            return datetime.fromisoformat(raw)
        if tag == "date":
            return date.fromisoformat(raw)
        if tag == "time":
            return time.fromisoformat(raw)
        if tag == "decimal":
            return Decimal(raw)
    return {key: _decode(item) for key, item in value.items()}


__all__ = ["CACHE_VERSION", "CachedFormatProbe", "digest", "dump_payload", "restore_document"]
