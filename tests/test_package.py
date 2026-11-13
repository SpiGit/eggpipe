"""Public API smoke tests."""

from __future__ import annotations

import eggpipe


def test_version() -> None:
    assert eggpipe.__version__ == "0.3.0"


def test_public_api_exports_core_models() -> None:
    for name in ("ModelDocument", "SourceModel", "ModelSlice", "FieldDef", "EnumDef", "UNSET"):
        assert name in eggpipe.__all__
        assert hasattr(eggpipe, name)
