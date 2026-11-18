"""Public API smoke tests."""

from __future__ import annotations

from importlib.metadata import version

import eggpipe


def test_version() -> None:
    assert eggpipe.__version__ == version("eggpipe")


def test_public_api_exports_core_models() -> None:
    for name in ("ModelDocument", "SourceModel", "ModelSlice", "FieldDef", "EnumDef", "UNSET"):
        assert name in eggpipe.__all__
        assert hasattr(eggpipe, name)
