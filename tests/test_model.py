"""Тесты моделей, UNSET и индексов."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from eggpipe import (
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


def test_unset_is_omitted_from_dump() -> None:
    unset = FieldDef(name="value", type="string")
    explicit_null = FieldDef(name="value", type="string", nullable=True, default=None)
    assert "default" not in unset.model_dump()
    assert "default" in explicit_null.model_dump()
    assert explicit_null.model_dump()["default"] is None


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


def test_entity_updated_at_round_trip_preserves_type() -> None:
    moment = datetime(2000, 1, 1, 0, 0)
    model = SourceModel(entities=(Entity(name="User", updated_at=moment),))
    restored = SourceModel.model_validate(model.model_dump(mode="json"))
    assert restored.entities[0].updated_at == moment
    assert isinstance(restored.entities[0].updated_at, datetime)

    day = date(2000, 1, 1)
    model = SourceModel(entities=(Entity(name="User", updated_at=day),))
    restored = SourceModel.model_validate(model.model_dump(mode="json"))
    assert restored.entities[0].updated_at == day
    assert type(restored.entities[0].updated_at) is date
