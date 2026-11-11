"""Реестр форматов документов."""

from __future__ import annotations

from dataclasses import dataclass

from metadata_generator.interfaces.formats import EntityModelFormat, FormatPlugin
from metadata_generator.utils.exceptions import (
    FormatConflictError,
    UnknownFormatError,
)


@dataclass(frozen=True)
class FormatInfo:
    name: str
    versions: tuple[str, ...]
    primitive_types: frozenset[str]


class FormatRegistry:
    """Встроенный entity-model и форматы от плагинов."""

    def __init__(self, *, include_builtin: bool = True) -> None:
        self._formats: dict[str, FormatPlugin] = {}
        if include_builtin:
            self.register(EntityModelFormat())

    def register(self, plugin: FormatPlugin) -> None:
        for name in plugin.format_names:
            if name == "entity-model" and not isinstance(plugin, EntityModelFormat):
                raise FormatConflictError(
                    "entity-model зарезервирован ядром и не может быть переопределён"
                )
            if name in self._formats:
                raise FormatConflictError(f"формат уже зарегистрирован: {name}")
            self._formats[name] = plugin

    def get(self, name: str) -> FormatPlugin:
        try:
            return self._formats[name]
        except KeyError as exc:
            raise UnknownFormatError(f"неизвестный формат: {name}") from exc

    def list(self) -> list[FormatInfo]:
        return [
            FormatInfo(
                name=name,
                versions=tuple(plugin.supported_versions),
                primitive_types=frozenset(plugin.primitive_types),
            )
            for name, plugin in sorted(self._formats.items())
        ]


__all__ = ["FormatInfo", "FormatRegistry"]
