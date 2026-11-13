#!/usr/bin/env python3
"""Generate AI documentation: llms.txt, manifest, schemas, diagnostics."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import eggpipe
from eggpipe.config.project_config import ProjectConfig
from eggpipe.core.document import ModelDocument
from eggpipe.engine.artifact_writer import Manifest
from eggpipe.engine.report import EngineReport

ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "docs" / "ai"
SCHEMA_DIR = AI_DIR / "schemas"
DIAGNOSTICS = ROOT / "docs" / "user" / "reference" / "diagnostics.md"

LLMS_FULL_SOURCES = (
    AI_DIR / "context.md",
    AI_DIR / "tasks.md",
    AI_DIR / "invariants.md",
    ROOT / "docs" / "user" / "quickstart.md",
    ROOT / "docs" / "user" / "concepts.md",
    ROOT / "docs" / "user" / "configuration.md",
    ROOT / "docs" / "user" / "cli.md",
    ROOT / "docs" / "user" / "api" / "index.md",
    ROOT / "docs" / "user" / "api" / "generator.md",
    ROOT / "docs" / "user" / "api" / "format.md",
    ROOT / "docs" / "user" / "api" / "models.md",
)

DOCUMENTS = (
    "docs/user/quickstart.md",
    "docs/user/tutorial.md",
    "docs/user/concepts.md",
    "docs/user/configuration.md",
    "docs/user/cli.md",
    "docs/user/api/index.md",
    "docs/user/api/generator.md",
    "docs/user/api/format.md",
    "docs/user/api/models.md",
    "docs/user/plugins.md",
    "docs/user/reference/diagnostics.md",
    "docs/user/troubleshooting.md",
    "docs/user/faq.md",
    "docs/ai/context.md",
    "docs/ai/tasks.md",
    "docs/ai/invariants.md",
    "docs/engineering/requirements/v2.2.md",
    "docs/engineering/system-design/index.md",
)

COMMANDS = (
    "eggpipe generate [MODELS] [-g ID] [--plan|--check] [--output-format json]",
    "eggpipe watch [MODELS] [-g ID] [--debounce-ms N]",
    "eggpipe init [PATH] --layout monolith|file-per-model|directory-per-model",
    "eggpipe config show|validate|schema",
    "eggpipe model validate|schema [--format NAME] [--version V]",
    "eggpipe gen list|info",
    "eggpipe format list|info",
    "eggpipe clean [--dry-run] [--yes] [--root PATH]",
)


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SCHEMA_DIR / "model.schema.json", _schema(ModelDocument))
    _write_json(SCHEMA_DIR / "config.schema.json", _schema(ProjectConfig))
    _write_json(SCHEMA_DIR / "report.schema.json", _schema(EngineReport))
    _write_json(SCHEMA_DIR / "manifest.schema.json", _schema(Manifest))
    _write_json(AI_DIR / "diagnostics.json", _diagnostics())
    _write_text(AI_DIR / "llms.txt", _llms_index())
    _write_text(AI_DIR / "llms-full.txt", _llms_full())
    _write_json(AI_DIR / "manifest.json", _manifest())


def _schema(model: type[Any]) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return model.model_json_schema()


def _diagnostics() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for line in DIAGNOSTICS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| EG"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        result.append(
            {
                "code": cells[0],
                "level": cells[1],
                "phase": cells[2],
                "message": cells[3],
                "status": cells[4],
            }
        )
    return result


def _llms_index() -> str:
    return """# Eggpipe documentation index

> Eggpipe generates artifacts from YAML model definitions. Current spec: v2.2.
> Project status: beta (0.x); breaking changes are possible before 1.0 (ADR-0014).

## User

- [Quick start](../user/quickstart.md)
- [Tutorial](../user/tutorial.md)
- [Concepts](../user/concepts.md)
- [Configuration](../user/configuration.md)
- [CLI](../user/cli.md)
- [API](../user/api/index.md)
- [Cookbook](../user/cookbook/index.md)
- [Plugins](../user/plugins.md)
- [Diagnostics](../user/reference/diagnostics.md)
- [Troubleshooting](../user/troubleshooting.md)

## AI

- [Context](context.md)
- [Tasks](tasks.md)
- [Invariants](invariants.md)
- [Manifest](manifest.json)
- [llms-full](llms-full.txt)

## Engineering

- [Requirements v2.2](../engineering/requirements/v2.2.md)
- [System Design](../engineering/system-design/index.md)
- [ADR index](../engineering/adr/index.md)
"""


def _llms_full() -> str:
    parts = ["# Eggpipe — full AI context\n"]
    for path in LLMS_FULL_SOURCES:
        parts.append(f"\n---\n\n<!-- source: {path.relative_to(ROOT)} -->\n\n")
        parts.append(path.read_text(encoding="utf-8"))
    return "".join(parts)


def _manifest() -> dict[str, Any]:
    return {
        "project": "eggpipe",
        "status": "beta",
        "spec_version": "2.2",
        "package_version": eggpipe.__version__,
        "public_api": sorted(eggpipe.__all__),
        "commands": list(COMMANDS),
        "documents": [{"path": path, "exists": (ROOT / path).is_file()} for path in DOCUMENTS],
        "artifacts": {
            "llms": "docs/ai/llms.txt",
            "llms_full": "docs/ai/llms-full.txt",
            "diagnostics": "docs/ai/diagnostics.json",
            "schemas": [
                "docs/ai/schemas/model.schema.json",
                "docs/ai/schemas/config.schema.json",
                "docs/ai/schemas/report.schema.json",
                "docs/ai/schemas/manifest.schema.json",
            ],
        },
    }


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    main()
