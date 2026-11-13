"""Тесты срезов модели."""

from __future__ import annotations

from eggpipe import (
    CustomType,
    Entity,
    EnumDef,
    EnumValue,
    FieldDef,
    InputSelection,
    SourceModel,
    select_slice,
)


def build_model() -> SourceModel:
    return SourceModel(
        entities=(
            Entity(
                name="User",
                fields=(FieldDef(name="id", type="Id"), FieldDef(name="role", type="Role")),
            ),
            Entity(name="Post", fields=(FieldDef(name="id", type="Id"),)),
        ),
        enums=(
            EnumDef(name="Role", values=(EnumValue(name="admin"),)),
            EnumDef(name="Unused", values=(EnumValue(name="x"),)),
        ),
        types=(CustomType(name="Id", base="integer"), CustomType(name="Other", base="string")),
    )


def test_no_selection_returns_all() -> None:
    model = build_model()
    result, diagnostics = select_slice(model)
    assert result.entities == model.entities
    assert result.enums == model.enums
    assert result.types == model.types
    assert diagnostics == []


def test_entity_selection_includes_referenced_types() -> None:
    result, diagnostics = select_slice(
        build_model(),
        InputSelection(entities=("User",), enums=("Unused",), types=("Other",)),
    )
    assert [item.name for item in result.entities] == ["User"]
    assert [item.name for item in result.enums] == ["Role", "Unused"]
    assert [item.name for item in result.types] == ["Id", "Other"]
    assert diagnostics == []


def test_unknown_names() -> None:
    result, diagnostics = select_slice(
        build_model(), InputSelection(entities=("Missing",), enums=("Nope",))
    )
    assert result.entities == ()
    assert {item.code for item in diagnostics} == {"MG018"}


def test_custom_type_closure() -> None:
    model = SourceModel(
        entities=(Entity(name="User", fields=(FieldDef(name="id", type="A"),)),),
        types=(
            CustomType(name="A", base="B"),
            CustomType(name="B", base="integer"),
            CustomType(name="C", base="string"),
        ),
    )
    result, diagnostics = select_slice(model, InputSelection(entities=("User",), types=("A",)))
    assert [item.name for item in result.types] == ["A", "B"]
    assert diagnostics == []
