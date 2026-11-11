"""Metadata Generator — публичный API ядра v0.1."""

from __future__ import annotations

from metadata_generator.core.document import ImportSpec, ModelDocument
from metadata_generator.core.model import (
    PRIMITIVE_TYPES,
    UNSET,
    Constraints,
    CustomType,
    Entity,
    EnumDef,
    EnumValue,
    ExtendsRef,
    FieldDef,
    InputSelection,
    ModelSlice,
    SourceModel,
)
from metadata_generator.core.naming import NamingStyle, transform
from metadata_generator.core.parser import Parser, normalize_version
from metadata_generator.core.slicing import select_slice
from metadata_generator.core.validator import validate_document, validate_entity_model
from metadata_generator.engine.format_registry import FormatInfo, FormatRegistry
from metadata_generator.interfaces.diagnostics import Diagnostic, DiagnosticLocation
from metadata_generator.interfaces.formats import EntityModelFormat, FormatPlugin
from metadata_generator.utils.exceptions import (
    ConfigValidationError,
    DocumentError,
    FormatConflictError,
    MetadataGeneratorError,
    UnknownFormatError,
)

__version__ = "0.1.0"

__all__ = [
    "PRIMITIVE_TYPES",
    "UNSET",
    "ConfigValidationError",
    "Constraints",
    "CustomType",
    "Diagnostic",
    "DiagnosticLocation",
    "DocumentError",
    "Entity",
    "EntityModelFormat",
    "EnumDef",
    "EnumValue",
    "ExtendsRef",
    "FieldDef",
    "FormatConflictError",
    "FormatInfo",
    "FormatPlugin",
    "FormatRegistry",
    "ImportSpec",
    "InputSelection",
    "MetadataGeneratorError",
    "ModelDocument",
    "ModelSlice",
    "NamingStyle",
    "Parser",
    "SourceModel",
    "UnknownFormatError",
    "normalize_version",
    "select_slice",
    "transform",
    "validate_document",
    "validate_entity_model",
]
