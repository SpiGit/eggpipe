"""Исключения ядра."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override


class MetadataGeneratorError(Exception):
    """Базовая ошибка библиотеки."""


class DocumentError(MetadataGeneratorError):
    """Ошибка чтения или разбора документа модели."""

    def __init__(self, code: str, path: Path | None, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(self.__str__())

    @override
    def __str__(self) -> str:
        location = f"{self.path}: " if self.path is not None else ""
        return f"{location}{self.code}: {self.message}"


class ConfigValidationError(MetadataGeneratorError):
    """Ошибка конфигурации."""


class FormatConflictError(ConfigValidationError):
    """Конфликт регистрации формата."""


class UnknownFormatError(ConfigValidationError):
    """Формат не найден в реестре."""


class LookupError(MetadataGeneratorError):
    """Имя не найдено в модели."""
