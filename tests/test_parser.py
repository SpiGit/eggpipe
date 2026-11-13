"""Тесты YAML-парсера и entity-model."""

from __future__ import annotations

from pathlib import Path

import pytest

from eggpipe import (
    UNSET,
    FormatInfo,
    Parser,
)
from eggpipe.utils.exceptions import DocumentError

VALID = """\
format: entity-model
version: "1.0"
model:
  name: Demo
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
          description: Identifier
        - name: nickname
          type: string
          nullable: true
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def code(path: Path) -> str:
    with pytest.raises(DocumentError) as caught:
        Parser().parse_document(path)
    return caught.value.code


def test_parse_valid_document(tmp_path: Path) -> None:
    path = write(tmp_path, VALID)
    document = Parser().parse_document(path)
    assert document.format == "entity-model"
    assert document.version == "1.0"
    assert document.model.name == "Demo"
    assert document.model.entity("User").fields[0].default is UNSET
    assert document.model.entity("User").fields[1].default is UNSET
    assert document.model.entity("User").source == path
    assert document.model.entity("User").format == "entity-model"
    assert document.model.entity("User").format_version == "1.0"
    assert document.model.formats == frozenset({FormatInfo(name="entity-model", version="1.0")})
    assert "source" not in document.model.entity("User").model_dump()


def test_numeric_version_is_normalized(tmp_path: Path) -> None:
    document = Parser().parse_document(write(tmp_path, VALID.replace('"1.0"', "1.0")))
    assert document.version == "1.0"


def test_missing_format(tmp_path: Path) -> None:
    assert code(write(tmp_path, VALID.replace("format: entity-model\n", ""))) == "MG007"


def test_unknown_format(tmp_path: Path) -> None:
    assert code(write(tmp_path, VALID.replace("entity-model", "unknown"))) == "MG007"


def test_missing_version_uses_latest(tmp_path: Path) -> None:
    document = Parser().parse_document(write(tmp_path, VALID.replace('version: "1.0"\n', "")))
    assert document.version == "1.0"


def test_invalid_version_type(tmp_path: Path) -> None:
    path = write(tmp_path, VALID.replace('version: "1.0"', "version: true"))
    assert code(path) == "MG008"


def test_unsupported_version(tmp_path: Path) -> None:
    assert code(write(tmp_path, VALID.replace('"1.0"', '"2.0"'))) == "MG008"


def test_duplicate_keys(tmp_path: Path) -> None:
    text = VALID + "  name: Other\n"
    assert code(write(tmp_path, text)) == "MG000"


def test_multiple_documents(tmp_path: Path) -> None:
    text = VALID + "---\nmodel: {}\n"
    assert code(write(tmp_path, text)) == "MG000"


def test_non_mapping_root(tmp_path: Path) -> None:
    assert code(write(tmp_path, "- item\n")) == "MG000"


def test_imports_are_parsed(tmp_path: Path) -> None:
    text = VALID.replace(
        "model:\n",
        "model:\n  imports:\n    - path: ./other.yaml\n    - path: ./icon.svg\n      as: icon\n",
    )
    document = Parser().parse_document(write(tmp_path, text))
    assert [item.kind for item in document.imports] == ["yaml", "resource"]


def test_extends_is_parsed(tmp_path: Path) -> None:
    text = VALID.replace(
        "    - name: User\n      fields:\n",
        "    - name: User\n      extends: Base\n      fields:\n",
    )
    document = Parser().parse_document(write(tmp_path, text))
    assert document.model.entity("User").extends == "Base"
