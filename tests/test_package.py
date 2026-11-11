"""Smoke-тесты пакета до появления публичного API."""

from __future__ import annotations

import metadata_generator


def test_version() -> None:
    assert metadata_generator.__version__ == "0.1.0"


def test_public_api_is_empty_for_now() -> None:
    assert metadata_generator.__all__ == []
