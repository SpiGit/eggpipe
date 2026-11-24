"""Path-free document payload for the L2 parse cache (ADR-0020)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from eggpipe.core.document import ModelDocument
from eggpipe.core.model import SourceModel

CACHE_VERSION = 2
_TAG = "__eggpipe_type__"
_MAPPING = "mapping"


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
        items = {key: _encode(item) for key, item in value.items()}
        if _TAG in value:
            return {_TAG: _MAPPING, "value": items}
        return items
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
    """Decode a tagged payload; malformed tags raise so ``load()`` treats them as a miss.

    Dicts that carry the tag key are escaped by :func:`_encode` as ``mapping``,
    so a tag-shaped user dict is never mistaken for a scalar.
    """
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get(_TAG)
    if tag is None or set(value) != {_TAG, "value"}:
        return {key: _decode(item) for key, item in value.items()}
    raw = value["value"]
    if tag == _MAPPING:
        if not isinstance(raw, dict):
            raise ValueError("cache mapping payload is not a mapping")
        return {key: _decode(item) for key, item in raw.items()}
    if not isinstance(raw, str):
        raise ValueError(f"cache scalar payload {tag!r} is not a string")
    if tag == "datetime":
        return datetime.fromisoformat(raw)
    if tag == "date":
        return date.fromisoformat(raw)
    if tag == "time":
        return time.fromisoformat(raw)
    if tag == "decimal":
        return Decimal(raw)
    raise ValueError(f"unknown cache type tag: {tag!r}")


__all__ = ["CACHE_VERSION", "CachedFormatProbe", "digest", "dump_payload", "restore_document"]
