#!/usr/bin/env python3
"""Small, dependency-free benchmark for the TPC-H example."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from eggpipe import (
    AppConfig,
    Engine,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    Parser,
    ProjectConfigLoader,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "tpc-h"


class NoopGenerator(GeneratorPlugin):
    """Generator that measures orchestration without artifact writing."""

    id = "tpch"
    name = "Noop"
    input_formats: ClassVar[set[str] | None] = None

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult()


def _median_ms(samples: list[float]) -> float:
    return statistics.median(samples) * 1000


def _run_config(iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        ProjectConfigLoader().load(EXAMPLE / ".eggpipe.yaml")
        samples.append(time.perf_counter() - started)
    return samples


def _run_parse(iterations: int) -> list[float]:
    parser = Parser()
    path = EXAMPLE / "model" / "region" / "base.yaml"
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        parser.parse_document(path)
        samples.append(time.perf_counter() - started)
    return samples


def _run_build(iterations: int) -> tuple[list[float], dict[str, list[float]]]:
    samples: list[float] = []
    phases: dict[str, list[float]] = {}
    for _ in range(iterations):
        engine = Engine(
            AppConfig(),
            ProjectConfigLoader().load(EXAMPLE / ".eggpipe.yaml"),
            config_dir=EXAMPLE,
            generators={"tpch": NoopGenerator()},
        )
        started = time.perf_counter()
        report = engine.build()
        samples.append(time.perf_counter() - started)
        if not report.success:
            raise SystemExit(f"benchmark build failed: {report.diagnostics}")
        for name, value in report.timings.items():
            phases.setdefault(name, []).append(float(value))
    return samples, phases


def _render(iterations: int, rows: list[tuple[str, float]], phases: dict[str, float]) -> str:
    lines = [
        "# Benchmarks",
        "",
        f"- Дата: {datetime.now(UTC).date().isoformat()}",
        f"- Python: {platform.python_version()}",
        f"- Платформа: {platform.platform()}",
        f"- Итераций: {iterations}",
        "- Пример: `examples/tpc-h`",
        "",
        "| Сценарий | Медиана, мс |",
        "|----------|-------------|",
    ]
    lines.extend(f"| {name} | {value:.3f} |" for name, value in rows)
    if phases:
        lines.extend(["", "| Фаза `build()` | Медиана, мс |", "|----------------|-------------|"])
        lines.extend(f"| {name} | {value:.3f} |" for name, value in phases.items())
    lines.extend(
        [
            "",
            "Числа зависят от машины и не являются гарантией производительности.",
            "Запуск: `uv run python tools/benchmark.py --iterations 20`.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the TPC-H example")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", type=Path, help="write Markdown to this path")
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    warmup = min(2, args.iterations)
    for _ in range(warmup):
        _run_config(1)
        _run_parse(1)
        _run_build(1)

    config = _run_config(args.iterations)
    parse = _run_parse(args.iterations)
    build, phase_samples = _run_build(args.iterations)
    phases = {
        name: statistics.median(values)
        for name, values in phase_samples.items()
    }
    rows = [
        ("config load", _median_ms(config)),
        ("parse one document", _median_ms(parse)),
        ("Engine.build (TPC-H)", _median_ms(build)),
    ]
    text = _render(args.iterations, rows, phases)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"written: {args.output}")
    else:
        print(text)
    print(json.dumps({"iterations": args.iterations, "rows": dict(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
