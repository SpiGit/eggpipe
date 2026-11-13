"""Eggpipe — публичный API ядра v0.1."""

from __future__ import annotations

from eggpipe.config.app_config import AppConfig
from eggpipe.config.generator_rules import (
    GeneratorConfig,
    GeneratorRules,
    GeneratorRulesLoader,
    SourceConfig,
)
from eggpipe.core.composition import Composition, CompositionResult
from eggpipe.core.document import ImportSpec, ModelDocument
from eggpipe.core.model import (
    PRIMITIVE_TYPES,
    UNSET,
    Constraints,
    CustomType,
    Entity,
    EntityIdentity,
    EnumDef,
    EnumValue,
    ExtendsRef,
    FieldDef,
    FieldIdentity,
    FormatInfo,
    FormatSchema,
    InputSelection,
    MergePolicy,
    ModelSlice,
    SourceModel,
)
from eggpipe.core.naming import NamingStyle, transform
from eggpipe.core.parser import Parser, normalize_version
from eggpipe.core.provenance import Provenance, git_provenance
from eggpipe.core.slicing import select_slice
from eggpipe.core.validator import validate_document, validate_entity_model
from eggpipe.engine.engine import Engine
from eggpipe.engine.format_registry import FormatRegistry
from eggpipe.engine.report import ArtifactReport, EngineReport, GeneratorReport
from eggpipe.interfaces.diagnostics import Diagnostic, DiagnosticLocation
from eggpipe.interfaces.formats import EntityModelFormat, FormatPlugin
from eggpipe.interfaces.generator import (
    Artifact,
    GenerationContext,
    GenerationResult,
    GeneratorInput,
    GeneratorPlugin,
    ImportedFile,
)
from eggpipe.utils.exceptions import (
    ArtifactPathError,
    ConfigValidationError,
    DocumentError,
    EggpipeError,
    FormatConflictError,
    FormatInheritanceError,
    LockError,
    ManifestError,
    UnknownFormatError,
)
from eggpipe.version import __version__

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
    "EggpipeError",
    "Engine",
    "EngineReport",
    "Entity",
    "EntityIdentity",
    "EntityModelFormat",
    "EnumDef",
    "EnumValue",
    "ExtendsRef",
    "FieldDef",
    "FieldIdentity",
    "FormatConflictError",
    "FormatInfo",
    "FormatInheritanceError",
    "FormatPlugin",
    "FormatRegistry",
    "FormatSchema",
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
    "MergePolicy",
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
