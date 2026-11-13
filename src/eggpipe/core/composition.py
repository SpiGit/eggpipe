"""Композиция документов по ADR-0001."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eggpipe.core.discovery import ModelUnit, SourceGroup
from eggpipe.core.document import ImportSpec, ModelDocument
from eggpipe.core.layers import merge_model_layers
from eggpipe.core.model import (
    CustomType,
    Entity,
    EnumDef,
    ExtendsRef,
    SourceModel,
)
from eggpipe.core.parser import Parser
from eggpipe.interfaces.diagnostics import Diagnostic, error
from eggpipe.interfaces.generator import ImportedFile
from eggpipe.utils.exceptions import DocumentError

MAX_IMPORT_DEPTH = 10
MAX_EXTENDS_DEPTH = 10


@dataclass(frozen=True)
class CompositionResult:
    model: SourceModel
    imports: dict[str, ImportedFile]
    documents: tuple[ModelDocument, ...]
    format: str
    version: str
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class ResolveState:
    project_root: Path
    allow_outside: bool
    cache: dict[Path, ModelDocument] = field(default_factory=dict)
    order: list[Path] = field(default_factory=list)
    closures: dict[Path, set[Path]] = field(default_factory=dict)
    aliases: dict[Path, dict[str, Path]] = field(default_factory=dict)
    resources: dict[str, ImportedFile] = field(default_factory=dict)
    resource_aliases: set[str] = field(default_factory=set)
    alias_names: dict[Path, set[str]] = field(default_factory=dict)


class Composition:
    def __init__(
        self,
        parser: Parser,
        *,
        project_root: Path,
        allow_outside: bool = False,
    ) -> None:
        self.parser = parser
        self.project_root = project_root.resolve()
        self.allow_outside = allow_outside

    def resolve(
        self,
        sources: list[Path],
        groups: list[SourceGroup] | None = None,
        *,
        resources: dict[str, ImportedFile] | None = None,
    ) -> CompositionResult:
        unit_refs = _unit_refs(sources, groups)
        if not unit_refs:
            raise DocumentError("MG000", None, "нет источников модели")
        state = ResolveState(
            project_root=self.project_root,
            allow_outside=self.allow_outside,
            resources=dict(resources or {}),
            resource_aliases=set(resources or {}),
        )
        diagnostics: list[Diagnostic] = []
        root_format: str | None = None
        root_version: str | None = None
        visited_keys: list[Path] = []
        grouped: dict[int, tuple[SourceGroup, list[Path]]] = {}
        for group, unit in unit_refs:
            keys = self._visit_unit(unit, state, root_format, root_version, diagnostics)
            if not keys:
                continue
            visited_keys.extend(keys)
            if group is not None:
                _, group_keys = grouped.setdefault(id(group), (group, []))
                group_keys.extend(keys)
            if root_format is None:
                first_document = state.cache[keys[0]]
                root_format = first_document.format
                root_version = first_document.version
        if not visited_keys:
            raise DocumentError("MG000", None, "нет источников модели")

        resolved = self._resolve_extends(state)
        selections = self._selections(state, list(grouped.values()), diagnostics)
        entities: list[Entity] = []
        enums: list[EnumDef] = []
        types: list[CustomType] = []
        seen_entities: set[str] = set()
        seen_enums: set[str] = set()
        seen_types: set[str] = set()
        for path in state.order:
            document = state.cache[path]
            entity_names, enum_names, type_names = selections.get(path, (None, None, None))
            for entity in document.model.entities:
                if entity_names is not None and entity.name not in entity_names:
                    continue
                if entity.name in seen_entities:
                    raise DocumentError(
                        "MG002",
                        path,
                        f"дубликат имени entity после композиции: {entity.name}",
                    )
                seen_entities.add(entity.name)
                entities.append(resolved[path][entity.name])
            for enum in document.model.enums:
                if enum_names is not None and enum.name not in enum_names:
                    continue
                if enum.name in seen_enums:
                    raise DocumentError(
                        "MG002",
                        path,
                        f"дубликат имени enum после композиции: {enum.name}",
                    )
                seen_enums.add(enum.name)
                enums.append(enum)
            for custom_type in document.model.types:
                if type_names is not None and custom_type.name not in type_names:
                    continue
                if custom_type.name in seen_types:
                    raise DocumentError(
                        "MG002",
                        path,
                        f"дубликат имени type после композиции: {custom_type.name}",
                    )
                seen_types.add(custom_type.name)
                types.append(custom_type)

        first = state.cache[visited_keys[0]]
        model = SourceModel(
            name=first.model.name,
            description=first.model.description,
            entities=tuple(entities),
            enums=tuple(enums),
            types=tuple(types),
        )
        return CompositionResult(
            model=model,
            imports=dict(state.resources),
            documents=tuple(state.cache[path] for path in state.order),
            format=first.format,
            version=first.version,
            diagnostics=diagnostics,
        )

    def _selections(
        self,
        state: ResolveState,
        grouped: list[tuple[SourceGroup, list[Path]]],
        diagnostics: list[Diagnostic],
    ) -> dict[Path, tuple[set[str] | None, set[str] | None, set[str] | None]]:
        result: dict[Path, tuple[set[str] | None, set[str] | None, set[str] | None]] = {}
        for group, keys in grouped:
            documents = [state.cache[key] for key in keys if key in state.cache]
            if not documents:
                continue
            entities = [item.name for document in documents for item in document.model.entities]
            enums = [item.name for document in documents for item in document.model.enums]
            types = [item.name for document in documents for item in document.model.types]
            location = group.paths[0].resolve() if group.paths else None
            selection = (
                _selected(group.input.entities, entities, "entities", location, diagnostics),
                _selected(group.input.enums, enums, "enums", location, diagnostics),
                _selected(group.input.types, types, "types", location, diagnostics),
            )
            for key in keys:
                result.setdefault(key, selection)
        return result

    def _visit_unit(
        self,
        unit: ModelUnit,
        state: ResolveState,
        root_format: str | None,
        root_version: str | None,
        diagnostics: list[Diagnostic],
    ) -> tuple[Path, ...]:
        if not unit.layered:
            keys: list[Path] = []
            for path in unit.paths:
                canonical = path.resolve()
                document = self._visit(canonical, state, (), root_format, root_version)
                if unit.single_entity and len(document.model.entities) != 1:
                    raise DocumentError(
                        "MG031",
                        canonical,
                        "файл file-per-model должен содержать одну сущность",
                    )
                if root_format is None:
                    root_format = document.format
                    root_version = document.version
                keys.append(canonical)
            return tuple(keys)

        documents = [self.parser.parse_document(path.resolve()) for path in unit.paths]
        merged = merge_model_layers(documents, self.parser.registry)
        diagnostics.extend(merged.diagnostics)
        document = merged.document
        self._ensure_compatible(document, root_format, root_version, document.path)
        key = (unit.model_dir or unit.paths[0].parent).resolve()
        state.cache[key] = document
        state.order.append(key)
        state.closures[key] = {key}
        state.aliases[key] = {}
        state.alias_names[key] = set()
        return (key,)

    def _visit(
        self,
        path: Path,
        state: ResolveState,
        stack: tuple[Path, ...],
        root_format: str | None,
        root_version: str | None,
    ) -> ModelDocument:
        canonical = path.resolve()
        if canonical in stack:
            cycle = " → ".join(item.name for item in (*stack, canonical))
            raise DocumentError("MG006", canonical, f"циклический импорт: {cycle}")
        if len(stack) > MAX_IMPORT_DEPTH:
            raise DocumentError("MG006", canonical, "глубина импорта больше 10")
        cached = state.cache.get(canonical)
        if cached is not None:
            self._ensure_compatible(cached, root_format, root_version, canonical)
            return cached

        document = self.parser.parse_document(canonical)
        self._ensure_compatible(document, root_format, root_version, canonical)
        state.cache[canonical] = document
        closure = {canonical}
        aliases: dict[str, Path] = {}
        aliases_seen: set[str] = set()

        for spec in document.imports:
            resolved = self._resolve_import_path(document, spec, state)
            if spec.kind == "resource":
                self._register_resource(spec, resolved, aliases_seen, state)
                continue
            alias = spec.alias or resolved.stem
            if alias in state.resource_aliases:
                raise DocumentError("MG032", canonical, f"alias ресурса уже занят: {alias}")
            if alias in aliases_seen:
                raise DocumentError("MG025", canonical, f"дубликат alias импорта: {alias}")
            aliases_seen.add(alias)
            aliases[alias] = resolved
            imported = self._visit(
                resolved,
                state,
                (*stack, canonical),
                root_format or document.format,
                root_version or document.version,
            )
            self._ensure_compatible(imported, document.format, document.version, resolved)
            closure |= state.closures[resolved]

        state.closures[canonical] = closure
        state.aliases[canonical] = aliases
        state.alias_names[canonical] = aliases_seen
        state.order.append(canonical)
        return document

    def _ensure_compatible(
        self,
        document: ModelDocument,
        root_format: str | None,
        root_version: str | None,
        path: Path,
    ) -> None:
        if root_format is not None and document.format != root_format:
            raise DocumentError("MG007", path, "импортированный документ имеет другой format")
        if root_version is not None and document.version != root_version:
            raise DocumentError("MG008", path, "импортированный документ имеет другую version")

    def _resolve_import_path(
        self,
        document: ModelDocument,
        spec: ImportSpec,
        state: ResolveState,
    ) -> Path:
        raw = Path(spec.path)
        if raw.is_absolute():
            raise DocumentError("MG022", document.path, f"абсолютный импорт запрещён: {spec.path}")
        resolved = (document.path.parent / raw).resolve()
        if not state.allow_outside and not resolved.is_relative_to(state.project_root):
            raise DocumentError("MG022", document.path, f"импорт вне project root: {spec.path}")
        if not resolved.is_file():
            raise DocumentError("MG000", document.path, f"импорт не найден: {spec.path}")
        return resolved

    def _register_resource(
        self,
        spec: ImportSpec,
        resolved: Path,
        aliases_seen: set[str],
        state: ResolveState,
    ) -> None:
        alias = spec.alias
        if not alias:
            raise DocumentError("MG025", resolved, "у resource-импорта обязателен alias")
        if alias in state.resource_aliases:
            raise DocumentError("MG032", resolved, f"alias ресурса уже занят: {alias}")
        if alias in aliases_seen or alias in state.resources:
            raise DocumentError("MG025", resolved, f"дубликат alias импорта: {alias}")
        aliases_seen.add(alias)
        try:
            content = resolved.read_bytes()
        except OSError as exc:
            raise DocumentError("MG000", resolved, f"не удалось прочитать ресурс: {exc}") from exc
        state.resources[alias] = ImportedFile(name=alias, path=resolved, content=content)

    def _resolve_extends(self, state: ResolveState) -> dict[Path, dict[str, Entity]]:
        memo: dict[tuple[Path, str], Entity] = {}
        result: dict[Path, dict[str, Entity]] = {path: {} for path in state.order}
        for path in state.order:
            for entity in state.cache[path].model.entities:
                result[path][entity.name] = self._resolve_entity(path, entity, state, memo, ())
        return result

    def _resolve_entity(
        self,
        doc_path: Path,
        entity: Entity,
        state: ResolveState,
        memo: dict[tuple[Path, str], Entity],
        stack: tuple[tuple[Path, str], ...],
    ) -> Entity:
        key = (doc_path, entity.name)
        if key in memo:
            return memo[key]
        if key in stack:
            raise DocumentError("MG009", doc_path, f"цикл extends: {entity.name}")
        if len(stack) > MAX_EXTENDS_DEPTH:
            raise DocumentError("MG009", doc_path, "глубина extends больше 10")
        if entity.extends is None:
            memo[key] = entity
            return entity

        parent_path, parent = self._find_parent(doc_path, entity.extends, state)
        resolved_parent = self._resolve_entity(
            parent_path,
            parent,
            state,
            memo,
            (*stack, key),
        )
        if len({field.name for field in entity.fields}) != len(entity.fields):
            raise DocumentError("MG003", doc_path, f"дубликат поля в {entity.name}")
        overrides = {field.name: field for field in entity.fields}
        fields = tuple(overrides.pop(field.name, field) for field in resolved_parent.fields)
        fields += tuple(field for field in entity.fields if field.name in overrides)
        merged = entity.model_copy(update={"fields": fields, "extends": None})
        memo[key] = merged
        return merged

    def _find_parent(
        self,
        doc_path: Path,
        extends: str | ExtendsRef,
        state: ResolveState,
    ) -> tuple[Path, Entity]:
        if isinstance(extends, ExtendsRef):
            target = state.aliases.get(doc_path, {}).get(extends.import_)
            if target is None:
                raise DocumentError(
                    "MG009", doc_path, f"неизвестный import alias: {extends.import_}"
                )
            for entity in state.cache[target].model.entities:
                if entity.name == extends.entity:
                    return target, entity
            raise DocumentError(
                "MG009",
                doc_path,
                f"entity {extends.entity} не найдена в import {extends.import_}",
            )

        candidates: list[tuple[Path, Entity]] = []
        for path in state.closures[doc_path]:
            for entity in state.cache[path].model.entities:
                if entity.name == extends:
                    candidates.append((path, entity))
        if not candidates:
            raise DocumentError("MG009", doc_path, f"родитель extends не найден: {extends}")
        if len(candidates) > 1:
            raise DocumentError("MG009", doc_path, f"неоднозначный extends: {extends}")
        return candidates[0]


def _unit_refs(
    sources: list[Path],
    groups: list[SourceGroup] | None,
) -> list[tuple[SourceGroup | None, ModelUnit]]:
    if groups is None:
        return [(None, ModelUnit(paths=(source.resolve(),))) for source in sources]
    result: list[tuple[SourceGroup | None, ModelUnit]] = []
    for group in groups:
        units = group.units or (ModelUnit(paths=group.paths),)
        for unit in units:
            if unit.paths:
                result.append((group, unit))
    return result


__all__ = ["Composition", "CompositionResult"]


def _selected(
    requested: tuple[str, ...] | None,
    available: list[str],
    label: str,
    path: Path | None,
    diagnostics: list[Diagnostic],
) -> set[str] | None:
    if not requested:
        return None
    available_set = set(available)
    for name in requested:
        if name not in available_set:
            diagnostics.append(
                error(
                    "MG018",
                    f"неизвестное имя в sources[].input.{label}: {name}",
                    file=path,
                )
            )
    return set(requested)
