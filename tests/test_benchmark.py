"""Tests for benchmark rendering helpers."""

from __future__ import annotations

from tools.benchmark import _cache_row, _median_ms, _render

from eggpipe.engine.report import CacheMissReasons, CacheReport, EngineReport


def test_median_ms() -> None:
    assert _median_ms([0.001, 0.003, 0.002]) == 2.0


def test_render_contains_rows() -> None:
    report = EngineReport.model_construct(
        cache=CacheReport(
            hits=7,
            misses=1,
            miss_reasons=CacheMissReasons(changed=1),
            entries=8,
            bytes=12829,
        )
    )
    text = _render(
        10,
        {"generate full": 12.5, "generate incremental no-op": 1.25},
        {"full": {"parse_ms": 3.0}, "no-op": {"parse_ms": 0.0}, "changed": {}},
        {"no-op": report},
    )
    assert "| generate full | 12.50 |" in text
    assert "| generate incremental no-op | 1.25 |" in text
    assert "| parse_ms | 3 | 0 | n/a |" in text
    assert "| no-op | hits=7, misses=1 (changed=1, missing=0, invalid=0, version=0)" in text
    assert "Итераций: 10" in text


def test_cache_row_without_metrics() -> None:
    report = EngineReport.model_construct(cache=None)
    assert _cache_row("no-op", report) == "| no-op | n/a |"
