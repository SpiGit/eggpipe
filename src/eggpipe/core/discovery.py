"""Discovery файлов моделей для sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eggpipe.config.generator_rules import GeneratorRules
from eggpipe.core.model import InputSelection
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning
from eggpipe.utils.yaml import YamlLoadError, load_yaml

SKIP_PARTS = {".git", ".eggpipe", "__pycache__", ".venv", "node_modules"}


@dataclass(frozen=True)
class SourceGroup:
    paths: tuple[Path, ...]
    input: InputSelection


@dataclass
class DiscoveredSources:
    paths: list[Path] = field(default_factory=list)
    groups: list[SourceGroup] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


def discover_sources(rules: GeneratorRules, config_dir: Path) -> DiscoveredSources:
    result = DiscoveredSources()
    seen: set[Path] = set()
    output_dirs = {(config_dir / item.output_dir).resolve() for item in rules.generators}

    for source in rules.sources:
        root = (config_dir / source.path).resolve()
        if not root.exists():
            result.diagnostics.append(
                error("MG000", f"source не найден: {source.path}", path=str(root))
            )
            continue
        candidates = [root] if root.is_file() else _walk_directory(root, output_dirs)
        group_paths: list[Path] = []
        for candidate in candidates:
            if root.is_dir() and not _is_model_document(candidate):
                result.diagnostics.append(
                    error(
                        "MG023",
                        "YAML в sources не является документом модели",
                        path=str(candidate),
                    )
                )
                continue
            canonical = candidate.resolve()
            if canonical in seen:
                result.diagnostics.append(
                    warning("MG024", "дубликат resolved-пути source", path=str(canonical))
                )
                continue
            seen.add(canonical)
            result.paths.append(canonical)
            group_paths.append(canonical)
        if group_paths:
            result.groups.append(SourceGroup(paths=tuple(group_paths), input=source.input))
    return result


def _is_model_document(path: Path) -> bool:
    try:
        data = load_yaml(path)
    except YamlLoadError:
        # Синтаксис и duplicate keys диагностирует Parser с MG000.
        return True
    return bool(data.get("format")) and data.get("version") is not None


def _walk_directory(root: Path, output_dirs: set[Path]) -> list[Path]:
    found: list[Path] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file() or candidate.suffix.lower() not in {".yaml", ".yml"}:
            continue
        relative = candidate.relative_to(root)
        if any(part.startswith(".") or part in SKIP_PARTS for part in relative.parts):
            continue
        resolved = candidate.resolve()
        if any(
            resolved == directory or resolved.is_relative_to(directory) for directory in output_dirs
        ):
            continue
        found.append(candidate)
    return sorted(found, key=lambda path: path.as_posix())


__all__ = ["DiscoveredSources", "SourceGroup", "discover_sources"]
