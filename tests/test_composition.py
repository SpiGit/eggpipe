"""Тесты композиции imports/extends."""

from __future__ import annotations

from pathlib import Path

import pytest

from metadata_generator import Composition, GeneratorConfig, GeneratorRules, Parser, SourceConfig
from metadata_generator.core.discovery import discover_sources
from metadata_generator.utils.exceptions import DocumentError


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def doc(body: str) -> str:
    return f'format: entity-model\nversion: "1.0"\nmodel:\n{body}'


def test_imports_merge_and_extends(tmp_path: Path) -> None:
    write(
        tmp_path / "base.yaml",
        doc(
            """\
  entities:
    - name: Audit
      fields:
        - name: id
          type: integer
        - name: created_at
          type: datetime
"""
        ),
    )
    main = write(
        tmp_path / "main.yaml",
        doc(
            """\
  imports:
    - path: ./base.yaml
      as: audit
  entities:
    - name: Post
      extends: Audit
      fields:
        - name: id
          type: string
        - name: title
          type: string
"""
        ),
    )
    result = Composition(Parser(), project_root=tmp_path).resolve([main])
    post = result.model.entity("Post")
    assert [field.name for field in post.fields] == ["id", "created_at", "title"]
    assert post.fields[0].type == "string"
    assert post.extends is None
    assert result.model.entity("Audit").fields[0].type == "integer"


def test_explicit_extends_and_resource(tmp_path: Path) -> None:
    write(
        tmp_path / "base.yaml",
        doc(
            "  entities:\n"
            "    - name: Audit\n"
            "      fields:\n"
            "        - name: id\n"
            "          type: integer\n"
        ),
    )
    (tmp_path / "icon.svg").write_text("<svg/>", encoding="utf-8")
    main = write(
        tmp_path / "main.yaml",
        doc(
            """\
  imports:
    - path: ./base.yaml
      as: audit
    - path: ./icon.svg
      as: icon
  entities:
    - name: Post
      extends:
        import: audit
        entity: Audit
      fields:
        - name: title
          type: string
"""
        ),
    )
    result = Composition(Parser(), project_root=tmp_path).resolve([main])
    assert result.model.entity("Post").fields[0].name == "id"
    assert result.imports["icon"].content == b"<svg/>"


def test_cycle_and_outside_root(tmp_path: Path) -> None:
    a = write(tmp_path / "a.yaml", doc("  imports:\n    - path: ./b.yaml\n"))
    write(tmp_path / "b.yaml", doc("  imports:\n    - path: ./a.yaml\n"))
    with pytest.raises(DocumentError) as cycle:
        Composition(Parser(), project_root=tmp_path).resolve([a])
    assert cycle.value.code == "MG006"

    outside = write(tmp_path.parent / "outside.yaml", doc("  entities: []\n"))
    root = write(
        tmp_path / "root.yaml",
        doc(f"  imports:\n    - path: ../{outside.name}\n"),
    )
    with pytest.raises(DocumentError) as escaped:
        Composition(Parser(), project_root=tmp_path).resolve([root])
    assert escaped.value.code == "MG022"


def test_duplicate_names(tmp_path: Path) -> None:
    write(tmp_path / "a.yaml", doc("  entities:\n    - name: User\n"))
    write(tmp_path / "b.yaml", doc("  entities:\n    - name: User\n"))
    main = write(
        tmp_path / "main.yaml",
        doc("  imports:\n    - path: ./a.yaml\n    - path: ./b.yaml\n"),
    )
    with pytest.raises(DocumentError) as error:
        Composition(Parser(), project_root=tmp_path).resolve([main])
    assert error.value.code == "MG002"


def test_ambiguous_short_extends(tmp_path: Path) -> None:
    write(tmp_path / "a.yaml", doc("  entities:\n    - name: Base\n"))
    write(tmp_path / "b.yaml", doc("  entities:\n    - name: Base\n"))
    main = write(
        tmp_path / "main.yaml",
        doc(
            """\
  imports:
    - path: ./a.yaml
    - path: ./b.yaml
  entities:
    - name: Child
      extends: Base
"""
        ),
    )
    with pytest.raises(DocumentError) as error:
        Composition(Parser(), project_root=tmp_path).resolve([main])
    assert error.value.code == "MG009"


def test_discover_directory_and_skip_output(tmp_path: Path) -> None:
    models = tmp_path / "models"
    write(models / "b.yaml", doc("  entities:\n    - name: B\n"))
    write(models / "a.yaml", doc("  entities:\n    - name: A\n"))
    write(models / ".hidden.yaml", doc("  entities:\n    - name: Hidden\n"))
    write(models / "out" / "generated.yaml", doc("  entities:\n    - name: Generated\n"))
    rules = GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("models")),),
        generators=(GeneratorConfig(id="demo", output_dir=Path("models/out")),),
    )
    discovered = discover_sources(rules, tmp_path)
    assert [path.name for path in discovered.paths] == ["a.yaml", "b.yaml"]
    assert discovered.diagnostics == []
