"""Тесты моделей, UNSET и индексов."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from metadata_generator import (
    UNSET,
    Constraints,
    CustomType,
    Entity,
    EnumDef,
    EnumValue,
    FieldDef,
    ModelSlice,
    SourceModel,
)


def test_unset_differs_from_explicit_null() -> None:
    unset = FieldDef(name="value", type="string")
    explicit_null = FieldDef(name="value", type="string", nullable=True, default=None)
    assert unset.default is UNSET
    assert explicit_null.default is None
    assert unset != explicit_null


def test_models_are_frozen() -> None:
    field = FieldDef(name="value", type="string")
    with pytest.raises(ValidationError):
        field.name = "other"  # type: ignore[misc]


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldDef(name="value", type="string", typo=True)  # type: ignore[call-arg]


def test_constraints() -> None:
    constraints = Constraints(min=1, max=10, pattern=r"^\d+$")
    field = FieldDef(name="value", type="integer", constraints=constraints)
    assert field.constraints is not None
    assert field.constraints.min == 1


def test_indexes_and_resolve_type() -> None:
    model = ModelSlice(
        entities=(Entity(name="User", fields=(FieldDef(name="id", type="Id"),)),),
        enums=(EnumDef(name="Role", values=(EnumValue(name="admin"),)),),
        types=(CustomType(name="Id", base="integer"),),
    )
    assert model.entity("User").name == "User"
    assert model.enum("Role").name == "Role"
    assert model.type("Id").base == "integer"
    assert isinstance(model.resolve_type(FieldDef(name="role", type="Role")), EnumDef)
    assert model.resolve_type(FieldDef(name="name", type="string")) == "string"


def test_source_model_metadata_is_independent() -> None:
    first = SourceModel()
    second = SourceModel()
    first.metadata["x"] = 1
    assert second.metadata == {}
