"""Document format contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import ValidationError
from typing_extensions import override

from eggpipe.core.document import ImportSpec, ModelDocument
from eggpipe.core.model import PRIMITIVE_TYPES, Entity, FormatSchema, LayerEntity, SourceModel
from eggpipe.interfaces.diagnostics import Diagnostic
from eggpipe.utils.exceptions import DocumentError


class FormatPlugin(ABC):
    """Document format: parser and validator."""

    api_version: ClassVar[Literal["1"]] = "1"
    format_names: ClassVar[list[str]]
    supported_versions: ClassVar[list[str]]
    extends: ClassVar[str | None] = None
    base_versions: ClassVar[dict[str, str]] = {}
    primitive_types: ClassVar[set[str]]
    schemas: ClassVar[dict[str, FormatSchema]]

    @abstractmethod
    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        """Build a document from a YAML mapping."""

    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        return []


class EntityModelFormat(FormatPlugin):
    """Built-in entity-model format."""

    format_names: ClassVar[list[str]] = ["entity-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    primitive_types: ClassVar[set[str]] = set(PRIMITIVE_TYPES)
    schemas: ClassVar[dict[str, FormatSchema]] = {
        "1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity)
    }

    def parse(self, raw: dict[str, Any], base_path: Path) -> ModelDocument:
        model_raw = raw.get("model", {})
        if not isinstance(model_raw, dict):
            raise DocumentError("EG000", base_path, "`model` must be a mapping")

        imports = self._parse_imports(model_raw.get("imports", []), base_path)
        model_data = {key: value for key, value in model_raw.items() if key != "imports"}
        try:
            model = SourceModel.model_validate(model_data)
        except ValidationError as exc:
            raise DocumentError("EG028", base_path, _format_validation_error(exc)) from exc

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
        """Hook for format plugins that extend entity-model."""

    @override
    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        from eggpipe.core.validator import validate_entity_model

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
            raise DocumentError("EG000", base_path, "`model.imports` must be a list")

        result: list[ImportSpec] = []
        for item in raw_imports:
            if not isinstance(item, dict):
                raise DocumentError("EG000", base_path, "imports entry must be a mapping")
            path_value = item.get("path")
            if not isinstance(path_value, str) or not path_value:
                raise DocumentError("EG000", base_path, "an import requires path")
            suffix = Path(path_value).suffix.lower()
            kind: Literal["yaml", "resource"] = (
                "yaml" if suffix in {".yaml", ".yml"} else "resource"
            )
            alias_value = item.get("as")
            alias = alias_value if isinstance(alias_value, str) else None
            if kind == "yaml" and alias is None:
                alias = Path(path_value).stem
            if kind == "resource" and not alias:
                raise DocumentError("EG025", base_path, "a resource import requires `as`")
            result.append(ImportSpec(path=path_value, alias=alias, kind=kind))
        return tuple(result)


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item["loc"])
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


__all__ = ["EntityModelFormat", "FormatPlugin"]
