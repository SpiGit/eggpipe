"""Core exceptions."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override


class EggpipeError(Exception):
    """Base library error."""


class DocumentError(EggpipeError):
    """Model document read or parse error."""

    def __init__(self, code: str, path: Path | None, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(self.__str__())

    @override
    def __str__(self) -> str:
        location = f"{self.path}: " if self.path is not None else ""
        return f"{location}{self.code}: {self.message}"


class ConfigValidationError(EggpipeError):
    """Configuration error."""


class FormatConflictError(ConfigValidationError):
    """Format registration conflict."""


class FormatInheritanceError(ConfigValidationError):
    """Format inheritance contract violated (EG034)."""

    code = "EG034"


class PluginContractError(ConfigValidationError):
    """Plugin contract violated."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class UnknownFormatError(ConfigValidationError):
    """Format not found in the registry."""


class ArtifactPathError(EggpipeError):
    """Invalid artifact path or content."""


class ManifestError(EggpipeError):
    """Manifest error."""


class LockError(EggpipeError):
    """output_dir is already used by another run."""
