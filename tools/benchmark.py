#!/usr/bin/env python3
"""Regression benchmark for the TPC-H example.

Measures the full generate path and the incremental path (L1 report cache and L2
document cache) on a temporary copy of ``examples/tpc-h`` so the repository state
is never touched. Numbers are medians of the requested iterations after a warm-up.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from eggpipe import AppConfig, Engine, EngineReport, ProjectConfigLoader

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "tpc-h"
CHANGED_DOC = Path("model") / "orders" / "base.yaml"
EXCLUDED = (".eggpipe", "generated")
DEFAULT_ITERATIONS = 20

SAMPLE_NAMES = ("full", "no-op", "changed")


def _median_ms(samples: list[float]) -> float:
    return statistics.median(samples) * 1000


def _copy_example(target: Path) -> Path:
    root = target / "tpc-h"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns(*EXCLUDED))
    return root


def _generate(root: Path, *, incremental: bool) -> tuple[float, EngineReport]:
    config = AppConfig(incremental=incremental)
    engine = Engine(config, ProjectConfigLoader().load(root / ".eggpipe.yaml"), config_dir=root)
    started = time.perf_counter()
    report = engine.generate()
    elapsed = time.perf_counter() - started
    if not report.success:
        raise SystemExit(f"benchmark generate failed: {report.diagnostics}")
    return elapsed, report


def _measure_config(iterations: int) -> float:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        ProjectConfigLoader().load(EXAMPLE / ".eggpipe.yaml")
        samples.append(time.perf_counter() - started)
    return _median_ms(samples)


def _measure_parse(iterations: int) -> float:
    engine = Engine(
        AppConfig(), ProjectConfigLoader().load(EXAMPLE / ".eggpipe.yaml"), config_dir=EXAMPLE
    )
    parser = engine.parser
    path = EXAMPLE / CHANGED_DOC
    parser.parse_document(path)  # warm-up
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        parser.parse_document(path)
        samples.append(time.perf_counter() - started)
    return _median_ms(samples)


def _measure_full(root: Path, iterations: int) -> tuple[float, dict[str, float]]:
    samples: list[float] = []
    phases: list[dict[str, int]] = []
    for _ in range(iterations):
        elapsed, report = _generate(root, incremental=False)
        samples.append(elapsed)
        phases.append(report.timings)
    return _median_ms(samples), _median_phases(phases)


def _measure_noop(root: Path, iterations: int) -> tuple[float, dict[str, float], EngineReport]:
    _generate(root, incremental=True)  # warm-up: populate caches and artifacts
    samples: list[float] = []
    phases: list[dict[str, int]] = []
    reports: list[EngineReport] = []
    for _ in range(iterations):
        elapsed, report = _generate(root, incremental=True)
        samples.append(elapsed)
        phases.append(report.timings)
        reports.append(report)
    return _median_ms(samples), _median_phases(phases), reports[-1]


def _measure_changed(root: Path, iterations: int) -> tuple[float, dict[str, float], EngineReport]:
    doc = root / CHANGED_DOC
    original = doc.read_text(encoding="utf-8")
    samples: list[float] = []
    phases: list[dict[str, int]] = []
    reports: list[EngineReport] = []
    try:
        for index in range(iterations):
            doc.write_text(f"{original}\n# benchmark change {index}\n", encoding="utf-8")
            elapsed, report = _generate(root, incremental=True)
            samples.append(elapsed)
            phases.append(report.timings)
            reports.append(report)
    finally:
        doc.write_text(original, encoding="utf-8")
    return _median_ms(samples), _median_phases(phases), reports[-1]


def _median_phases(phases: list[dict[str, int]]) -> dict[str, float]:
    names = sorted({name for phase in phases for name in phase})
    return {
        name: statistics.median(phase[name] for phase in phases if name in phase) for name in names
    }


def _cache_row(name: str, report: EngineReport) -> str:
    # ``cache`` exists only from report version 3 (eggpipe 0.5.0+); older releases
    # return n/a so the same script can measure the baseline.
    cache = getattr(report, "cache", None)
    if cache is None:
        return f"| {name} | n/a |"
    reasons = cache.miss_reasons
    reasons_text = (
        f"changed={reasons.changed}, missing={reasons.missing}, "
        f"invalid={reasons.invalid}, version={reasons.version}"
    )
    return (
        f"| {name} | hits={cache.hits}, misses={cache.misses} ({reasons_text}), "
        f"entries={cache.entries}, bytes={cache.bytes} B |"
    )


def _render(
    iterations: int,
    samples: dict[str, float],
    phases: dict[str, dict[str, float]],
    reports: dict[str, EngineReport],
) -> str:
    lines = [
        "## Регрессионные сценарии",
        "",
        f"- Дата: {datetime.now(UTC).date().isoformat()}",
        f"- Python: {platform.python_version()}",
        f"- Платформа: {platform.platform()}",
        f"- Итераций: {iterations}",
        "- Пример: `examples/tpc-h`, временная копия, реальный `tpch`-генератор",
        "",
        "| Сценарий | Медиана, мс |",
        "|----------|-------------|",
    ]
    lines.extend(f"| {name} | {value:.2f} |" for name, value in samples.items())
    lines.extend(["", "| Фаза `generate()` | full, мс | no-op, мс | changed 1/8, мс |"])
    lines.append("|-------------------|----------|-----------|-----------------|")
    phase_names = sorted({name for phase in phases.values() for name in phase})
    for name in phase_names:
        cells = []
        for sample in SAMPLE_NAMES:
            value = phases.get(sample, {}).get(name)
            cells.append("n/a" if value is None else f"{value:.0f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.extend(["", "| Сценарий | Кэш L2 |", "|----------|--------|"])
    for sample in ("no-op", "changed"):
        report = reports.get(sample)
        if report is not None:
            lines.append(_cache_row(sample, report))
    lines.extend(
        [
            "",
            "Числа зависят от машины и не являются гарантией производительности.",
            "Пороговые значения и базовая линия — `engineering/benchmarks.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark TPC-H generation scenarios")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--output", type=Path, help="write Markdown to this path")
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    with tempfile.TemporaryDirectory() as tmp:
        root = _copy_example(Path(tmp))

        config = _measure_config(args.iterations)
        parse = _measure_parse(args.iterations)
        warmup = min(2, args.iterations)
        for _ in range(warmup):
            _generate(root, incremental=False)

        full, full_phases = _measure_full(root, args.iterations)
        noop, noop_phases, noop_report = _measure_noop(root, args.iterations)
        changed, changed_phases, changed_report = _measure_changed(root, args.iterations)

    samples = {
        "config load": config,
        "parse one document": parse,
        "generate full": full,
        "generate incremental no-op": noop,
        "generate incremental changed 1 of 8": changed,
    }
    phases = {"full": full_phases, "no-op": noop_phases, "changed": changed_phases}
    reports = {"no-op": noop_report, "changed": changed_report}
    text = _render(args.iterations, samples, phases, reports)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"written: {args.output}")
    else:
        print(text)
    print(json.dumps({"iterations": args.iterations, "samples": samples}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
