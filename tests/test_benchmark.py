"""Tests for benchmark rendering helpers."""

from __future__ import annotations

from tools.benchmark import _median_ms, _render


def test_median_ms() -> None:
    assert _median_ms([0.001, 0.003, 0.002]) == 2.0


def test_render_contains_rows() -> None:
    text = _render(10, [("build", 12.5)], {"parse_ms": 3.0})
    assert "| build | 12.500 |" in text
    assert "| parse_ms | 3.000 |" in text
    assert "Итераций: 10" in text
