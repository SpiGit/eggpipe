"""Property-based tests for the parser and round-trip."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from eggpipe import (
    UNSET,
    CustomType,
    Entity,
    EntityModelFormat,
    EnumDef,
    EnumValue,
    FieldDef,
    SourceModel,
)
from eggpipe.utils.exceptions import DocumentError

NAMES = st.from_regex(r"^[A-Za-z_][A-Za-z0-9_]*$", fullmatch=True)
DEFAULTS = {
    "string": st.one_of(st.none(), st.text(), st.just(UNSET)),
    "integer": st.one_of(st.none(), st.integers(), st.just(UNSET)),
    "boolean": st.one_of(st.none(), st.booleans(), st.just(UNSET)),
    "date": st.one_of(st.none(), st.dates(), st.just(UNSET)),
    "datetime": st.one_of(st.none(), st.datetimes(), st.just(UNSET)),
}
JSON_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)
JSON_VALUE = st.recursive(
    JSON_SCALAR,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=8,
)


@st.composite
def field_defs(draw: st.DrawFn) -> FieldDef:
    type_name = draw(st.sampled_from(list(DEFAULTS)))
    return FieldDef(
        name=draw(NAMES),
        type=type_name,
        description=draw(st.none() | st.text()),
        required=draw(st.booleans()),
        nullable=draw(st.booleans()),
        default=draw(DEFAULTS[type_name]),
    )


@st.composite
def source_models(draw: st.DrawFn) -> SourceModel:
    entities = tuple(
        Entity(
            name=draw(NAMES),
            description=draw(st.none() | st.text()),
            updated_at=draw(st.none() | st.dates() | st.datetimes()),
            fields=tuple(draw(st.lists(field_defs(), max_size=4))),
        )
        for _ in range(draw(st.integers(min_value=0, max_value=3)))
    )
    enums = tuple(
        EnumDef(
            name=draw(NAMES),
            values=tuple(
                EnumValue(name=draw(NAMES), value=draw(st.none() | st.integers() | st.text()))
                for _ in range(draw(st.integers(min_value=0, max_value=3)))
            ),
        )
        for _ in range(draw(st.integers(min_value=0, max_value=2)))
    )
    types = tuple(
        CustomType(name=draw(NAMES), base=draw(st.sampled_from(["string", "integer"])))
        for _ in range(draw(st.integers(min_value=0, max_value=2)))
    )
    return SourceModel(entities=entities, enums=enums, types=types)


@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(model_raw=st.dictionaries(st.text(), JSON_VALUE, max_size=6))
def test_entity_model_parse_only_domain_errors(
    model_raw: dict[str, object], tmp_path: Path
) -> None:
    raw = {"format": "entity-model", "version": "1.0", "model": model_raw}
    try:
        EntityModelFormat().parse(raw, tmp_path)
    except DocumentError:
        pass
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"parser raised raw {type(exc).__name__}: {exc}")


@settings(max_examples=40)
@given(model=source_models())
def test_source_model_round_trip(model: SourceModel) -> None:
    dumped = model.model_dump(mode="json")
    restored = SourceModel.model_validate(dumped)
    assert restored == model
    assert all(
        "default" not in field.model_dump()
        for entity in model.entities
        for field in entity.fields
        if field.default is UNSET
    )


@settings(max_examples=20)
@given(
    value=st.one_of(st.none(), st.booleans(), st.integers(), st.text(), st.dates(), st.datetimes())
)
def test_field_defaults_are_stable(
    value: str | int | bool | date | datetime | None,
) -> None:
    type_name = (
        "date"
        if isinstance(value, date) and not isinstance(value, datetime)
        else "datetime"
        if isinstance(value, datetime)
        else "boolean"
        if isinstance(value, bool)
        else "integer"
        if isinstance(value, int)
        else "string"
    )
    field = FieldDef(name="value", type=type_name, default=value, nullable=value is None)
    dumped = field.model_dump(mode="json")
    restored = FieldDef.model_validate(dumped)
    assert restored.default == field.default


def test_date_and_datetime_round_trip() -> None:
    field = FieldDef(name="value", type="datetime", default=datetime(2026, 1, 1, 12, 30))
    restored = FieldDef.model_validate(field.model_dump(mode="json"))
    assert restored.default == datetime(2026, 1, 1, 12, 30)
    date_field = FieldDef(name="date", type="date", default=date(2026, 1, 1))
    assert FieldDef.model_validate(date_field.model_dump(mode="json")).default == date(2026, 1, 1)
