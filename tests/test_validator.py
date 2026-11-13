"""Тесты семантической валидации."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eggpipe import (
    UNSET,
    Constraints,
    CustomType,
    Entity,
    EnumDef,
    EnumValue,
    FieldDef,
    ModelDocument,
    SourceModel,
    validate_document,
    validate_entity_model,
)


def model_with(field: FieldDef) -> SourceModel:
    return SourceModel(entities=(Entity(name="Sample", fields=(field,)),))


def codes(model: SourceModel) -> list[str]:
    return [item.code for item in validate_entity_model(model)]


@pytest.mark.parametrize(
    ("required", "nullable", "default", "codes_expected"),
    [
        (True, False, UNSET, []),
        (True, False, "x", []),
        (True, False, None, ["MG010"]),
        (True, True, UNSET, ["MG011"]),
        (True, True, "x", ["MG011"]),
        (True, True, None, ["MG011"]),
        (False, False, UNSET, []),
        (False, False, "x", []),
        (False, False, None, ["MG010"]),
        (False, True, UNSET, []),
        (False, True, "x", []),
        (False, True, None, []),
    ],
)
def test_null_matrix(
    required: bool,
    nullable: bool,
    default: Any,
    codes_expected: list[str],
) -> None:
    field = FieldDef(
        name="value",
        type="string",
        required=required,
        nullable=nullable,
        default=default,
        description="value" if required else None,
    )
    assert codes(model_with(field)) == codes_expected


def test_unknown_type() -> None:
    assert "MG004" in codes(model_with(FieldDef(name="x", type="Missing")))


def test_empty_primitive_types_are_honoured() -> None:
    model = model_with(FieldDef(name="x", type="string"))
    diagnostics = validate_entity_model(model, primitive_types=set())
    assert [item.code for item in diagnostics if item.code == "MG004"] == ["MG004"]


def test_duplicate_entity_names() -> None:
    model = SourceModel(
        entities=(Entity(name="User"), Entity(name="User")),
    )
    assert "MG002" in codes(model)


def test_duplicate_fields() -> None:
    model = model_with(FieldDef(name="x", type="string"))
    duplicated = model.model_copy(
        update={
            "entities": (
                model.entities[0].model_copy(
                    update={
                        "fields": (
                            FieldDef(name="x", type="string"),
                            FieldDef(name="x", type="integer"),
                        )
                    }
                ),
            )
        }
    )
    assert "MG003" in codes(duplicated)


def test_enum_validation() -> None:
    empty = SourceModel(enums=(EnumDef(name="Role"),))
    assert "MG019" in codes(empty)
    duplicated = SourceModel(
        enums=(
            EnumDef(
                name="Role",
                values=(EnumValue(name="a", value=1), EnumValue(name="b", value=1)),
            ),
        )
    )
    assert "MG019" in codes(duplicated)


def test_custom_type_cycle_and_unknown_base() -> None:
    cycle = SourceModel(
        types=(
            CustomType(name="A", base="B"),
            CustomType(name="B", base="A"),
        )
    )
    assert "MG020" in codes(cycle)
    unknown = SourceModel(types=(CustomType(name="A", base="Missing"),))
    assert "MG004" in codes(unknown)


def test_constraints_validation() -> None:
    pattern = model_with(FieldDef(name="x", type="integer", constraints=Constraints(pattern="[")))
    assert "MG021" in codes(pattern)
    bounds = model_with(FieldDef(name="x", type="integer", constraints=Constraints(min=10, max=1)))
    assert "MG021" in codes(bounds)


def test_default_type_and_enum() -> None:
    wrong_type = model_with(FieldDef(name="x", type="integer", default="no"))
    assert "MG016" in codes(wrong_type)
    enum = SourceModel(
        enums=(EnumDef(name="Role", values=(EnumValue(name="admin"),)),),
        entities=(
            Entity(name="User", fields=(FieldDef(name="role", type="Role", default="guest"),)),
        ),
    )
    assert "MG017" in codes(enum)


def test_default_constraints() -> None:
    model = model_with(
        FieldDef(
            name="x",
            type="string",
            default="abc",
            constraints=Constraints(min_length=5),
        )
    )
    assert "MG017" in codes(model)


def test_warnings() -> None:
    model = SourceModel(
        enums=(EnumDef(name="Unused", values=(EnumValue(name="a"),)),),
        entities=(
            Entity(
                name="lower",
                fields=(FieldDef(name="x", type="string", required=True),),
            ),
        ),
    )
    result = codes(model)
    assert "MG012" in result
    assert "MG013" in result
    assert "MG015" in result


def test_case_collision() -> None:
    model = SourceModel(
        entities=(Entity(name="User"),),
        enums=(EnumDef(name="user", values=(EnumValue(name="a"),)),),
    )
    assert "MG026" in codes(model)


def test_document_warns_about_imports() -> None:
    document = ModelDocument(
        format="entity-model",
        version="1.0",
        path=Path("model.yaml"),
        imports=(),
        model=SourceModel(),
    )
    assert validate_document(document) == []
