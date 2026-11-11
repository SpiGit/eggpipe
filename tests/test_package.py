"""Smoke-тесты публичного API."""

from __future__ import annotations

import metadata_generator


def test_version() -> None:
    assert metadata_generator.__version__ == "0.1.0"


def test_public_api_exports_core_models() -> None:
    for name in ("ModelDocument", "SourceModel", "ModelSlice", "FieldDef", "EnumDef", "UNSET"):
        assert name in metadata_generator.__all__
        assert hasattr(metadata_generator, name)
