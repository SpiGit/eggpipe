"""Metadata Generator — публичный API ядра v0.1."""

from __future__ import annotations

from metadata_generator.config.app_config import AppConfig
from metadata_generator.config.generator_rules import (
    GeneratorConfig,
    GeneratorRules,
    GeneratorRulesLoader,
    SourceConfig,
)
from metadata_generator.core.composition import Composition, CompositionResult
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
from metadata_generator.core.provenance import Provenance, git_provenance
from metadata_generator.core.slicing import select_slice
from metadata_generator.core.validator import validate_document, validate_entity_model
from metadata_generator.engine.engine import Engine
from metadata_generator.engine.format_registry import FormatInfo, FormatRegistry
from metadata_generator.engine.report import ArtifactReport, EngineReport, GeneratorReport
from metadata_generator.interfaces.diagnostics import Diagnostic, DiagnosticLocation
from metadata_generator.interfaces.formats import EntityModelFormat, FormatPlugin
from metadata_generator.interfaces.generator import (
    Artifact,
    GenerationContext,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    ImportedFile,
)
from metadata_generator.utils.exceptions import (
    ArtifactPathError,
    ConfigValidationError,
    DocumentError,
    FormatConflictError,
    LockError,
    ManifestError,
    MetadataGeneratorError,
    UnknownFormatError,
)
from metadata_generator.version import __version__

__all__ = [
    "PRIMITIVE_TYPES",
    "UNSET",
    "AppConfig",
    "Artifact",
    "ArtifactPathError",
    "ArtifactReport",
    "Composition",
    "CompositionResult",
    "ConfigValidationError",
    "Constraints",
    "CustomType",
    "Diagnostic",
    "DiagnosticLocation",
    "DocumentError",
    "Engine",
    "EngineReport",
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
    "GenerationContext",
    "GenerationResult",
    "GeneratorConfig",
    "GeneratorInput",
    "GeneratorPlugin",
    "GeneratorReport",
    "GeneratorRules",
    "GeneratorRulesLoader",
    "ImportSpec",
    "ImportedFile",
    "InputSelection",
    "LockError",
    "ManifestError",
    "MetadataGeneratorError",
    "ModelDocument",
    "ModelSlice",
    "NamingStyle",
    "Parser",
    "Provenance",
    "SourceConfig",
    "SourceModel",
    "UnknownFormatError",
    "__version__",
    "git_provenance",
    "normalize_version",
    "select_slice",
    "transform",
    "validate_document",
    "validate_entity_model",
]
