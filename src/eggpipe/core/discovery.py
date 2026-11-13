"""Discovery файлов моделей, model units и ресурсов."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from eggpipe.config.generator_rules import GeneratorRules, ResourceConfig, SourceConfig
from eggpipe.core.model import InputSelection
from eggpipe.interfaces.diagnostics import Diagnostic, error, warning
from eggpipe.interfaces.generator import ImportedFile
from eggpipe.utils.yaml import YamlLoadError, load_yaml

SKIP_PARTS = {".git", ".eggpipe", "__pycache__", ".venv", "node_modules"}
GLOB_CHARS = re.compile(r"[*?\[]")


@dataclass(frozen=True)
class ModelUnit:
    paths: tuple[Path, ...]
    layered: bool = False
    model_dir: Path | None = None
    single_entity: bool = False


@dataclass(frozen=True)
class SourceGroup:
    paths: tuple[Path, ...]
    input: InputSelection
    units: tuple[ModelUnit, ...] | None = None


@dataclass
class DiscoveredSources:
    paths: list[Path] = field(default_factory=list)
    groups: list[SourceGroup] = field(default_factory=list)
    resources: dict[str, ImportedFile] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)


def discover_sources(
    rules: GeneratorRules,
    config_dir: Path,
    *,
    allow_outside: bool = False,
) -> DiscoveredSources:
    result = DiscoveredSources()
    config_root = config_dir.resolve()
    output_dirs = {(config_root / item.output_dir).resolve() for item in rules.generators}
    _collect_resources(
        rules.resources,
        base=config_root,
        boundary=config_root,
        prefix=None,
        allow_outside=allow_outside,
        result=result,
    )

    seen: set[Path] = set()
    for source in rules.sources:
        root = (config_root / source.path).resolve()
        if not root.exists():
            result.diagnostics.append(
                error("MG000", f"source не найден: {source.path}", path=str(root))
            )
            continue
        if not root.is_relative_to(config_root):
            result.diagnostics.append(error("MG022", "source вне project root", path=str(root)))
            continue
        if source.layout == "monolith":
            _discover_monolith(root, source, seen, result)
        elif source.layout == "file-per-model":
            _discover_file_per_model(root, source, output_dirs, seen, config_root, result)
        else:
            _discover_directory_per_model(
                root,
                source,
                output_dirs,
                seen,
                allow_outside,
                config_root,
                result,
            )
    return result


def _discover_monolith(
    root: Path,
    source: SourceConfig,
    seen: set[Path],
    result: DiscoveredSources,
) -> None:
    if not root.is_file():
        result.diagnostics.append(
            error("MG000", f"monolith source должен быть файлом: {source.path}", path=str(root))
        )
        return
    canonical = root.resolve()
    if canonical in seen:
        result.diagnostics.append(
            warning("MG024", "дубликат resolved-пути source", path=str(canonical))
        )
        return
    seen.add(canonical)
    _check_resource_overlap([canonical], result)
    result.paths.append(canonical)
    unit = ModelUnit(paths=(canonical,))
    result.groups.append(SourceGroup(paths=(canonical,), input=source.input, units=(unit,)))


def _discover_file_per_model(
    root: Path,
    source: SourceConfig,
    output_dirs: set[Path],
    seen: set[Path],
    boundary: Path,
    result: DiscoveredSources,
) -> None:
    if not root.is_dir():
        result.diagnostics.append(
            error(
                "MG000",
                f"file-per-model source должен быть каталогом: {source.path}",
                path=str(root),
            )
        )
        return
    files = _match_files(root, source.files or (), output_dirs, result, boundary)
    canonical_files: list[Path] = []
    for path in files:
        canonical = path.resolve()
        if canonical in seen:
            result.diagnostics.append(
                warning("MG024", "дубликат resolved-пути source", path=str(canonical))
            )
            continue
        seen.add(canonical)
        result.paths.append(canonical)
        canonical_files.append(canonical)
    if canonical_files:
        _check_resource_overlap(canonical_files, result)
        units = tuple(ModelUnit(paths=(path,), single_entity=True) for path in canonical_files)
        result.groups.append(
            SourceGroup(paths=tuple(canonical_files), input=source.input, units=units)
        )


def _discover_directory_per_model(
    root: Path,
    source: SourceConfig,
    output_dirs: set[Path],
    seen: set[Path],
    allow_outside: bool,
    config_root: Path,
    result: DiscoveredSources,
) -> None:
    if not root.is_dir():
        result.diagnostics.append(
            error(
                "MG000",
                f"directory-per-model source должен быть каталогом: {source.path}",
                path=str(root),
            )
        )
        return
    model_dirs = _match_dirs(root, source.model_dirs or (), output_dirs, result, config_root)
    known = {path.name for path in model_dirs}
    unknown = sorted(set(source.models) - known)
    for name in unknown:
        result.diagnostics.append(
            error("MG037", f"models.{name} указывает на неизвестный каталог", path=str(root))
        )

    units: list[ModelUnit] = []
    group_paths: list[Path] = []
    for model_dir in model_dirs:
        override = source.models.get(model_dir.name)
        patterns = override.files if override is not None and override.files is not None else None
        files = _match_files(
            model_dir,
            patterns if patterns is not None else (source.files or ()),
            output_dirs,
            result,
            config_root,
        )
        if not files:
            result.diagnostics.append(
                warning("MG027", f"пустой каталог модели: {model_dir.name}", path=str(model_dir))
            )
            continue
        resources: list[Path] = []
        if override is not None and override.resources is not None:
            _collect_resources(
                override.resources,
                base=model_dir,
                boundary=model_dir,
                prefix=model_dir.name,
                allow_outside=allow_outside,
                result=result,
                collected=resources,
            )
        _check_resource_overlap(
            files,
            result,
            extra={path.resolve() for path in resources},
        )
        unique: list[Path] = []
        for path in files:
            canonical = path.resolve()
            if canonical in seen:
                result.diagnostics.append(
                    warning("MG024", "дубликат resolved-пути source", path=str(canonical))
                )
                continue
            seen.add(canonical)
            unique.append(canonical)
        if not unique:
            continue
        result.paths.extend(unique)
        group_paths.extend(unique)
        units.append(ModelUnit(paths=tuple(unique), layered=True, model_dir=model_dir))
    if units:
        result.groups.append(
            SourceGroup(paths=tuple(group_paths), input=source.input, units=tuple(units))
        )


def _match_files(
    root: Path,
    patterns: tuple[str, ...],
    output_dirs: set[Path],
    result: DiscoveredSources,
    boundary: Path,
) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        matches = _expand(root, pattern, result, expect="file")
        for path in matches:
            if _is_in_output(path, output_dirs):
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(boundary):
                result.diagnostics.append(
                    error("MG022", "файл модели вне project root", path=str(resolved))
                )
                continue
            if resolved.suffix.lower() in {".yaml", ".yml"} and not _is_model_document(resolved):
                result.diagnostics.append(
                    error("MG023", "YAML не является документом модели", path=str(resolved))
                )
                continue
            found[resolved] = None
    return [Path(path) for path in sorted(found, key=lambda item: item.as_posix())]


def _match_dirs(
    root: Path,
    patterns: tuple[str, ...],
    output_dirs: set[Path],
    result: DiscoveredSources,
    boundary: Path,
) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        matches = _expand(root, pattern, result, expect="dir")
        for path in matches:
            if _is_in_output(path, output_dirs):
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(boundary):
                result.diagnostics.append(
                    error("MG022", "каталог модели вне project root", path=str(resolved))
                )
                continue
            found[resolved] = None
    return [Path(path) for path in sorted(found, key=lambda item: item.as_posix())]


def _expand(
    root: Path,
    pattern: str,
    result: DiscoveredSources,
    *,
    expect: str,
) -> list[Path]:
    raw = Path(pattern)
    if raw.is_absolute():
        result.diagnostics.append(
            error("MG000", f"абсолютный путь в sources запрещён: {pattern}", path=str(root))
        )
        return []
    if GLOB_CHARS.search(pattern):
        matches = [
            path
            for path in root.glob(pattern)
            if (path.is_file() if expect == "file" else path.is_dir())
        ]
        matches = [path for path in matches if not _is_hidden(root, path)]
        if not matches:
            result.diagnostics.append(
                warning("MG036", f"glob не нашёл совпадений: {pattern}", path=str(root))
            )
        return sorted(matches, key=lambda item: item.as_posix())
    candidate = (root / raw).resolve()
    if expect == "file" and not candidate.is_file():
        result.diagnostics.append(error("MG000", f"файл не найден: {pattern}", path=str(candidate)))
        return []
    if expect == "dir" and not candidate.is_dir():
        result.diagnostics.append(
            error("MG000", f"каталог не найден: {pattern}", path=str(candidate))
        )
        return []
    if _is_hidden(root, candidate):
        return []
    return [candidate]


def _collect_resources(
    resources: tuple[ResourceConfig, ...],
    *,
    base: Path,
    boundary: Path,
    prefix: str | None,
    allow_outside: bool,
    result: DiscoveredSources,
    collected: list[Path] | None = None,
) -> None:
    for resource in resources:
        raw = resource.path
        if raw.is_absolute():
            result.diagnostics.append(
                error("MG000", f"абсолютный путь ресурса запрещён: {raw}", path=str(base))
            )
            continue
        pattern = raw.as_posix()
        if GLOB_CHARS.search(pattern):
            if resource.alias is not None:
                result.diagnostics.append(
                    error("MG032", "as допустим только для одного файла", path=pattern)
                )
                continue
            matches = [
                path for path in base.glob(pattern) if path.is_file() and not _is_hidden(base, path)
            ]
            if not matches:
                result.diagnostics.append(
                    warning(
                        "MG036",
                        f"glob ресурсов не нашёл совпадений: {pattern}",
                        path=str(base),
                    )
                )
            for path in sorted(matches, key=lambda item: item.as_posix()):
                _add_resource(
                    path,
                    base=base,
                    boundary=boundary,
                    prefix=prefix,
                    alias=None,
                    allow_outside=allow_outside,
                    result=result,
                    collected=collected,
                )
            continue

        candidate = (base / raw).resolve()
        if candidate.is_dir():
            if resource.alias is not None:
                result.diagnostics.append(
                    error("MG032", "as допустим только для одного файла", path=pattern)
                )
                continue
            files = sorted(
                (
                    path
                    for path in candidate.rglob("*")
                    if path.is_file() and not _is_hidden(candidate, path)
                ),
                key=lambda item: item.as_posix(),
            )
            for path in files:
                _add_resource(
                    path,
                    base=base,
                    boundary=boundary,
                    prefix=prefix,
                    alias=None,
                    allow_outside=allow_outside,
                    result=result,
                    collected=collected,
                )
            continue
        if not candidate.is_file():
            result.diagnostics.append(
                error("MG000", f"ресурс не найден: {pattern}", path=str(candidate))
            )
            continue
        _add_resource(
            candidate,
            base=base,
            boundary=boundary,
            prefix=prefix,
            alias=resource.alias,
            allow_outside=allow_outside,
            result=result,
            collected=collected,
        )


def _add_resource(
    path: Path,
    *,
    base: Path,
    boundary: Path,
    prefix: str | None,
    alias: str | None,
    allow_outside: bool,
    result: DiscoveredSources,
    collected: list[Path] | None,
) -> None:
    resolved = path.resolve()
    if not allow_outside and not resolved.is_relative_to(boundary.resolve()):
        result.diagnostics.append(
            error("MG022", "ресурс вне разрешённой границы", path=str(resolved))
        )
        return
    if collected is not None:
        collected.append(resolved)
    name = alias or _default_alias(base, resolved, prefix)
    if name in result.resources:
        result.diagnostics.append(
            error("MG032", f"дубликат alias ресурса: {name}", path=str(resolved))
        )
        return
    try:
        content = resolved.read_bytes()
    except OSError as exc:
        result.diagnostics.append(
            error("MG000", f"не удалось прочитать ресурс: {exc}", path=str(resolved))
        )
        return
    result.resources[name] = ImportedFile(name=name, path=resolved, content=content)


def _check_resource_overlap(
    files: list[Path],
    result: DiscoveredSources,
    *,
    extra: set[Path] | None = None,
) -> None:
    resources = {item.path.resolve() for item in result.resources.values()}
    if extra:
        resources |= extra
    overlap = {path.resolve() for path in files} & resources
    for path in sorted(overlap, key=lambda item: item.as_posix()):
        result.diagnostics.append(
            error(
                "MG038",
                "путь одновременно указан в files и resources",
                path=str(path),
            )
        )


def _is_model_document(path: Path) -> bool:
    try:
        data = load_yaml(path)
    except YamlLoadError:
        # Синтаксис и duplicate keys диагностирует Parser с MG000.
        return True
    return bool(data.get("format"))


def _default_alias(base: Path, path: Path, prefix: str | None) -> str:
    try:
        relative = path.relative_to(base.resolve()).with_suffix("").as_posix()
    except ValueError:
        relative = path.with_suffix("").as_posix()
    return f"{prefix}/{relative}" if prefix else relative


def _is_hidden(root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        relative = path
    return any(part.startswith(".") or part in SKIP_PARTS for part in relative.parts)


def _is_in_output(path: Path, output_dirs: set[Path]) -> bool:
    resolved = path.resolve()
    return any(
        resolved == directory or resolved.is_relative_to(directory) for directory in output_dirs
    )


__all__ = ["DiscoveredSources", "ModelUnit", "SourceGroup", "discover_sources"]
