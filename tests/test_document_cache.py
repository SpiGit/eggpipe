"""Tests for the internal document cache (ADR-0020)."""

from __future__ import annotations

import json
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typing_extensions import override

from eggpipe import DocumentError, EntityModelFormat, FormatRegistry
from eggpipe.core.cache import CACHE_VERSION, dump_payload, restore_document
from eggpipe.core.parser import Parser
from eggpipe.engine import document_cache
from eggpipe.engine.document_cache import CacheEntry, DocumentCache
from eggpipe.engine.parser_cache import CachedParser
from eggpipe.engine.plugin_loader import build_format_registry

DOC = """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
"""

IMPORTER = """\
format: entity-model
version: "1.0"
model:
  imports:
    - path: ./base.yaml
      as: base
  entities:
    - name: Post
"""

METADATA_DOC = DOC.replace(
    "      fields:", "      metadata:\n        created: 2024-01-01\n      fields:"
)

META = Path(".eggpipe") / "cache" / "meta.json"
DOCS = Path(".eggpipe") / "cache" / "docs"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def parse(path: Path):
    return Parser(build_format_registry()).parse_document(path)


def make_cache(
    root: Path,
    *,
    version: str = "0.0.0",
    registry: FormatRegistry | None = None,
) -> DocumentCache:
    return DocumentCache(
        config_dir=root,
        registry=registry or build_format_registry(),
        eggpipe_version=version,
    )


class ExtraInputFormat(EntityModelFormat):
    """Format whose declared inputs are not part of ``model.imports``."""

    format_names: ClassVar[list[str]] = ["entity-extra"]

    @override
    def input_paths(self, raw: dict[str, Any], base_path: Path) -> tuple[Path, ...]:
        return (base_path / "extra.txt",)


def prepared(tmp_path: Path, *, text: str = DOC, name: str = "user") -> Path:
    """Create a document, remember it and persist the cache."""
    path = write(tmp_path / "model" / f"{name}.yaml", text)
    cache = make_cache(tmp_path)
    cache.remember(path, parse(path))
    cache.persist()
    return path


def read_meta(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / META).read_text(encoding="utf-8"))


def test_payload_roundtrip_restores_path_fields(tmp_path: Path) -> None:
    path = write(tmp_path / "model/user.yaml", DOC)
    document = parse(path)

    restored = restore_document(dump_payload(document), path)

    assert restored.model_dump() == document.model_dump()
    assert restored.path == path
    entity = restored.model.entity("User")
    assert entity.source == path
    assert entity.format == "entity-model"
    assert entity.format_version == "1.0"
    assert entity.fields[0].source == path


def test_store_load_roundtrip(tmp_path: Path) -> None:
    path = prepared(tmp_path)

    loaded = make_cache(tmp_path).load(path)

    assert loaded is not None
    assert loaded.model_dump() == parse(path).model_dump()
    assert loaded.model.entity("User").source == path


def test_same_content_in_two_paths_restores_each_path(tmp_path: Path) -> None:
    first = write(tmp_path / "a/user.yaml", DOC)
    cache = make_cache(tmp_path)
    cache.remember(first, parse(first))
    cache.persist()
    second = write(tmp_path / "b/user.yaml", DOC)

    loaded_first = make_cache(tmp_path).load(first)
    loaded_second = make_cache(tmp_path).load(second)

    assert loaded_first is not None and loaded_second is not None
    assert loaded_first.model.entity("User").source == first
    assert loaded_second.model.entity("User").source == second


def test_eggpipe_version_mismatch_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path)

    assert make_cache(tmp_path, version="9.9.9").load(path) is None


def test_cache_version_mismatch_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    data = read_meta(tmp_path)
    data["cache_version"] = CACHE_VERSION + 1
    (tmp_path / META).write_text(json.dumps(data), encoding="utf-8")

    assert make_cache(tmp_path).load(path) is None


def test_plugin_version_mismatch_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    data = read_meta(tmp_path)
    next(iter(data["entries"].values()))["format_plugin_version"] = "changed"
    (tmp_path / META).write_text(json.dumps(data), encoding="utf-8")

    assert make_cache(tmp_path).load(path) is None


def test_closure_change_is_miss(tmp_path: Path) -> None:
    write(tmp_path / "model/base.yaml", DOC)
    path = prepared(tmp_path, text=IMPORTER, name="post")

    assert make_cache(tmp_path).load(path) is not None
    write(tmp_path / "model/base.yaml", DOC + "# changed\n")

    assert make_cache(tmp_path).load(path) is None


def test_outside_import_is_not_cached(tmp_path: Path) -> None:
    outside = write(tmp_path.parent / "outside.yaml", DOC)
    path = write(tmp_path / "model/post.yaml", IMPORTER.replace("./base.yaml", str(outside)))

    cache = make_cache(tmp_path)
    cache.remember(path, parse(path))
    cache.persist()

    assert not (tmp_path / META).exists()


def test_corrupt_meta_is_miss_and_recovers(tmp_path: Path) -> None:
    path = write(tmp_path / "model/user.yaml", DOC)
    (tmp_path / META).parent.mkdir(parents=True)
    (tmp_path / META).write_text("{not json", encoding="utf-8")

    assert make_cache(tmp_path).load(path) is None

    cache = make_cache(tmp_path)
    cache.remember(path, parse(path))
    cache.persist()
    assert make_cache(tmp_path).load(path) is not None


def test_corrupt_payload_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    payload = next((tmp_path / DOCS).glob("*.json"))
    payload.write_text("{not json", encoding="utf-8")

    assert make_cache(tmp_path).load(path) is None


def test_prune_removes_untouched_entries(tmp_path: Path) -> None:
    first = write(tmp_path / "model/first.yaml", DOC.replace("User", "First"))
    second = write(tmp_path / "model/second.yaml", DOC.replace("User", "Second"))
    cache = make_cache(tmp_path)
    cache.remember(first, parse(first))
    cache.persist()

    cache = make_cache(tmp_path)
    cache.remember(second, parse(second))
    cache.persist()

    assert len(read_meta(tmp_path)["entries"]) == 1
    assert len(list((tmp_path / DOCS).glob("*.json"))) == 1
    assert make_cache(tmp_path).load(first) is None
    assert make_cache(tmp_path).load(second) is not None


def test_unreadable_path_is_miss(tmp_path: Path) -> None:
    assert make_cache(tmp_path).load(tmp_path / "missing.yaml") is None


def test_entry_inputs_are_config_relative(tmp_path: Path) -> None:
    write(tmp_path / "shared/base.yaml", DOC)
    path = prepared(
        tmp_path,
        text=IMPORTER.replace("./base.yaml", "../shared/base.yaml"),
        name="post",
    )

    entry = CacheEntry.model_validate(next(iter(read_meta(tmp_path)["entries"].values())))
    assert path.is_file()
    assert list(entry.inputs) == ["shared/base.yaml"]


def test_declared_input_paths_not_in_imports_are_tracked(tmp_path: Path) -> None:
    extra = write(tmp_path / "model/extra.txt", "v1")
    path = write(
        tmp_path / "model/user.yaml",
        DOC.replace("format: entity-model", "format: entity-extra"),
    )
    registry = build_format_registry()
    registry.register(ExtraInputFormat())
    cache = make_cache(tmp_path, registry=registry)
    cache.remember(path, Parser(registry).parse_document(path))
    cache.persist()

    entry = CacheEntry.model_validate(next(iter(read_meta(tmp_path)["entries"].values())))
    assert entry.inputs == {"model/extra.txt": sha256(b"v1").hexdigest()}
    assert make_cache(tmp_path, registry=registry).load(path) is not None

    extra.write_text("v2", encoding="utf-8")
    assert make_cache(tmp_path, registry=registry).load(path) is None


def test_meta_input_outside_root_is_rejected(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    outside = write(tmp_path.parent / "outside-cache.yaml", "secret")
    data = read_meta(tmp_path)
    next(iter(data["entries"].values()))["inputs"] = {
        "../outside-cache.yaml": sha256(outside.read_bytes()).hexdigest()
    }
    (tmp_path / META).write_text(json.dumps(data), encoding="utf-8")

    assert make_cache(tmp_path).load(path) is None


def test_persisted_state_contains_no_paths(tmp_path: Path) -> None:
    prepared(tmp_path)
    meta_text = (tmp_path / META).read_text(encoding="utf-8")
    payload = json.loads(next((tmp_path / DOCS).glob("*.json")).read_text(encoding="utf-8"))

    assert str(tmp_path) not in meta_text
    assert str(tmp_path) not in json.dumps(payload)
    for entity in payload["model"]["entities"]:
        assert "source" not in entity and "path" not in entity
        assert all("source" not in field for field in entity["fields"])


def test_payload_roundtrip_preserves_scalar_types(tmp_path: Path) -> None:
    path = write(
        tmp_path / "model/event.yaml",
        """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: Event
      metadata:
        created: 2024-01-01
        updated: 2024-01-02 03:04:05
      fields:
        - name: start
          type: date
          constraints:
            min: 2024-01-01
            max: 2024-12-31
""",
    )
    document = parse(path)

    payload = json.loads(json.dumps(dump_payload(document)))
    restored = restore_document(payload, path)

    entity = restored.model.entity("Event")
    assert isinstance(entity.metadata["created"], date)
    assert isinstance(entity.metadata["updated"], datetime)
    constraints = entity.fields[0].constraints
    assert constraints is not None
    assert isinstance(constraints.min, date)
    assert isinstance(constraints.max, date)


def test_payload_roundtrip_keeps_user_tag_key(tmp_path: Path) -> None:
    path = write(
        tmp_path / "model/tagged.yaml",
        """\
format: entity-model
version: "1.0"
model:
  metadata:
    __eggpipe_type__: date
    value: "2024-01-01"
  entities:
    - name: Tagged
""",
    )
    document = parse(path)

    restored = restore_document(json.loads(json.dumps(dump_payload(document))), path)

    assert restored.model.metadata == {"__eggpipe_type__": "date", "value": "2024-01-01"}


def test_stored_user_tag_key_survives_roundtrip(tmp_path: Path) -> None:
    path = write(
        tmp_path / "model/tagged.yaml",
        """\
format: entity-model
version: "1.0"
model:
  metadata:
    __eggpipe_type__: datetime
    value: "2024-01-01 03:04:05"
  entities:
    - name: Tagged
""",
    )
    cache = make_cache(tmp_path)
    cache.remember(path, parse(path))
    cache.persist()

    loaded = make_cache(tmp_path).load(path)

    assert loaded is not None
    assert loaded.model.metadata == {
        "__eggpipe_type__": "datetime",
        "value": "2024-01-01 03:04:05",
    }


@pytest.mark.parametrize(
    ("tag", "value"),
    [
        ("date", "not-a-date"),
        ("decimal", "not-a-number"),
        ("decimal", {"not": "a string"}),
        ("unknown", "2024-01-01"),
    ],
)
def test_corrupt_tagged_payload_is_miss(tmp_path: Path, tag: str, value: Any) -> None:
    path = prepared(tmp_path, text=METADATA_DOC)
    payload_path = next((tmp_path / DOCS).glob("*.json"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    tagged = payload["model"]["entities"][0]["metadata"]["created"]
    tagged["__eggpipe_type__"] = tag
    tagged["value"] = value
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    cache = make_cache(tmp_path)

    assert cache.load(path) is None
    document = CachedParser(build_format_registry(), cache).parse_document(path)
    assert document.model.entity("User") is not None


def test_corrupt_mapping_payload_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path, text=METADATA_DOC)
    payload_path = next((tmp_path / DOCS).glob("*.json"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["model"]["entities"][0]["metadata"]["created"] = {
        "__eggpipe_type__": "mapping",
        "value": "not-a-mapping",
    }
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    cache = make_cache(tmp_path)

    assert cache.load(path) is None
    document = CachedParser(build_format_registry(), cache).parse_document(path)
    assert document.model.entity("User") is not None


def test_deeply_nested_payload_is_miss(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    payload_path = next((tmp_path / DOCS).glob("*.json"))
    payload_path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
    cache = make_cache(tmp_path)

    assert cache.load(path) is None
    assert CachedParser(build_format_registry(), cache).parse_document(path) is not None


def test_shared_import_digest_is_memoized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path / "model/base.yaml", DOC)
    first = write(tmp_path / "model/first.yaml", IMPORTER)
    second = write(tmp_path / "model/second.yaml", IMPORTER)
    calls: list[str] = []
    original = document_cache.digest

    def counting(content: bytes) -> str:
        calls.append(sha256(content).hexdigest())
        return original(content)

    monkeypatch.setattr(document_cache, "digest", counting)
    cache = make_cache(tmp_path)
    for path in (first, second):
        cache.remember(path, parse(path))

    base = sha256((tmp_path / "model/base.yaml").read_bytes()).hexdigest()
    assert calls.count(base) == 1


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("format: [", "EG000"),
        (DOC.replace('version: "1.0"', 'version: "9.9"'), "EG008"),
        (DOC.replace("          type: integer\n", ""), "EG028"),
    ],
)
def test_parse_error_is_not_cached(tmp_path: Path, text: str, code: str) -> None:
    path = write(tmp_path / "model/broken.yaml", text)
    with pytest.raises(DocumentError) as direct:
        parse(path)
    cache = make_cache(tmp_path)
    parser = CachedParser(build_format_registry(), cache)

    with pytest.raises(DocumentError) as cached:
        parser.parse_document(path)
    cache.persist()

    assert cached.value.code == direct.value.code == code
    assert cached.value.path == direct.value.path
    assert not (tmp_path / META).exists()


def test_invalid_entry_is_pruned(tmp_path: Path) -> None:
    path = prepared(tmp_path)
    data = read_meta(tmp_path)
    next(iter(data["entries"].values()))["format_plugin_version"] = "changed"
    (tmp_path / META).write_text(json.dumps(data), encoding="utf-8")

    cache = make_cache(tmp_path)
    assert cache.entry(path) is None
    cache.persist()

    assert read_meta(tmp_path)["entries"] == {}
    assert not list((tmp_path / DOCS).glob("*.json"))
