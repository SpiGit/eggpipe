"""Исключения ядра."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override


class EggpipeError(Exception):
    """Базовая ошибка библиотеки."""


class DocumentError(EggpipeError):
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


class ConfigValidationError(EggpipeError):
    """Ошибка конфигурации."""


class FormatConflictError(ConfigValidationError):
    """Конфликт регистрации формата."""


class FormatInheritanceError(ConfigValidationError):
    """Нарушен контракт наследования формата (MG034)."""

    code = "MG034"


class UnknownFormatError(ConfigValidationError):
    """Формат не найден в реестре."""


class LookupError(EggpipeError):
    """Имя не найдено в модели."""


class ArtifactPathError(EggpipeError):
    """Некорректный путь или содержимое артефакта."""


class ManifestError(EggpipeError):
    """Ошибка manifest."""


class LockError(EggpipeError):
    """output_dir уже используется другим запуском."""
