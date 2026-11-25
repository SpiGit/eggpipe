"""Tests for benchmark helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools import benchmark
from tools.benchmark import _cache_row, _copy_example, _median_ms, _median_phases, _render

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
        {"changed": report},
    )
    assert "| generate full | 12.50 |" in text
    assert "| generate incremental no-op | 1.25 |" in text
    assert "| parse_ms | 3 | 0 | n/a |" in text
    assert "| changed | hits=7, misses=1 (changed=1, missing=0, invalid=0, version=0)" in text
    assert "Итераций: 10" in text


def test_cache_row_without_metrics() -> None:
    report = EngineReport.model_construct(cache=None)
    assert _cache_row("no-op", report) == "| no-op | n/a |"


def test_measure_noop_has_no_extra_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = [EngineReport.model_construct(timings={"total_ms": index}) for index in range(3)]
    calls = 0

    def fake_generate(root: Path, *, incremental: bool) -> tuple[float, EngineReport]:
        nonlocal calls
        report = reports[calls]
        calls += 1
        return 0.0, report

    monkeypatch.setattr(benchmark, "_generate", fake_generate)

    _, _, report = benchmark._measure_noop(tmp_path, 2)

    assert calls == 3
    assert report is reports[-1]


def test_measure_changed_has_no_extra_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / benchmark.CHANGED_DOC
    doc.parent.mkdir(parents=True)
    doc.write_text("base\n", encoding="utf-8")
    reports = [EngineReport.model_construct(timings={"total_ms": index}) for index in range(2)]
    calls = 0

    def fake_generate(root: Path, *, incremental: bool) -> tuple[float, EngineReport]:
        nonlocal calls
        report = reports[calls]
        calls += 1
        return 0.0, report

    monkeypatch.setattr(benchmark, "_generate", fake_generate)

    _, _, report = benchmark._measure_changed(tmp_path, 2)

    assert calls == 2
    assert report is reports[-1]
    assert doc.read_text(encoding="utf-8") == "base\n"


def test_median_phases_uses_available_samples() -> None:
    phases = [{"parse_ms": 4, "total_ms": 10}, {"parse_ms": 2}, {"parse_ms": 6}]
    assert _median_phases(phases) == {"parse_ms": 4, "total_ms": 10}


def test_copy_example_skips_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    (source / ".eggpipe").mkdir(parents=True)
    (source / "generated").mkdir()
    (source / "model").mkdir()
    (source / "model" / "base.yaml").write_text("version: '1.0'\n", encoding="utf-8")
    monkeypatch.setattr(benchmark, "EXAMPLE", source)

    root = _copy_example(tmp_path / "target")

    assert (root / "model" / "base.yaml").is_file()
    assert not (root / ".eggpipe").exists()
    assert not (root / "generated").exists()
