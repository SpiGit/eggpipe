"""Контракты форматов документов."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Literal

import pydantic as pyd
from typing_extensions import override

from metadata_generator.core.document import ImportSpec, ModelDocument
from metadata_generator.core.model import PRIMITIVE_TYPES, SourceModel
from metadata_generator.interfaces.diagnostics import Diagnostic
from metadata_generator.utils.exceptions import DocumentError


class FormatPlugin(ABC):
    """Формат документа: парсер и валидатор."""

    api_version: ClassVar[Literal["1"]] = "1"
    format_names: ClassVar[list[str]]
    supported_versions: ClassVar[list[str]]
    primitive_types: ClassVar[set[str]]

    @abstractmethod
    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        """Построить документ из YAML-словаря."""

    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        return []


class EntityModelFormat(FormatPlugin):
    """Встроенный формат entity-model."""

    format_names: ClassVar[list[str]] = ["entity-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)

    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        model_raw = raw.get("model", {})
        if not isinstance(model_raw, dict):
            raise DocumentError("MG000", base_path, "`model` должен быть словарём")

        imports = self._parse_imports(model_raw.get("imports", []), base_path)
        model_data = {key: value for key, value in model_raw.items() if key != "imports"}
        try:
            model = SourceModel.model_validate(model_data)
        except pyd.ValidationError as exc:
            raise DocumentError("MG028", base_path, _format_validation_error(exc)) from exc

        document = ModelDocument(
            format=str(raw["format"]),
            version=str(raw["version"]),
            path=base_path,
            imports=imports,
            model=model,
            metadata=raw.get("metadata", {}),
        )
        self.parse_extensions(document, raw)
        return document

    def parse_extensions(self, document: ModelDocument, raw: dict[str, Any]) -> None:
        """Hook для format-плагинов, расширяющих entity-model."""

    @override
    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        from metadata_generator.core.validator import validate_entity_model

        diagnostics = validate_entity_model(
            document.model,
            primitive_types=self.primitive_types,
            file=document.path,
        )
        return diagnostics + self.validate_extensions(document)

    def validate_extensions(self, document: ModelDocument) -> list[Diagnostic]:
        return []

    def _parse_imports(self, raw_imports: object, base_path: Path) -> tuple[ImportSpec, ...]:
        if raw_imports is None:
            return ()
        if not isinstance(raw_imports, list):
            raise DocumentError("MG000", base_path, "`model.imports` должен быть списком")

        result: list[ImportSpec] = []
        for item in raw_imports:
            if not isinstance(item, dict):
                raise DocumentError("MG000", base_path, "элемент imports должен быть словарём")
            path_value = item.get("path")
            if not isinstance(path_value, str) or not path_value:
                raise DocumentError("MG000", base_path, "у импорта обязателен path")
            suffix = Path(path_value).suffix.lower()
            kind: Literal["yaml", "resource"] = (
                "yaml" if suffix in {".yaml", ".yml"} else "resource"
            )
            alias_value = item.get("as")
            alias = alias_value if isinstance(alias_value, str) else None
            if kind == "yaml" and alias is None:
                alias = Path(path_value).stem
            if kind == "resource" and not alias:
                raise DocumentError("MG025", base_path, "у resource-импорта обязателен `as`")
            result.append(ImportSpec(path=path_value, alias=alias, kind=kind))
        return tuple(result)


def _format_validation_error(exc: pyd.ValidationError) -> str:
    parts = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item["loc"])
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


__all__ = ["EntityModelFormat", "FormatPlugin"]
