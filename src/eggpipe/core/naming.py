"""Утилиты именования; переименование модели остаётся решением плагина."""

from __future__ import annotations

import re
from enum import StrEnum


class NamingStyle(StrEnum):
    SNAKE = "snake_case"
    CAMEL = "camelCase"
    PASCAL = "pascal_case"
    KEBAB = "kebab-case"


def transform(name: str, style: NamingStyle) -> str:
    """Детерминированно преобразовать имя в выбранный стиль."""
    words = _split_words(name)
    if not words:
        return name
    if style is NamingStyle.SNAKE:
        return "_".join(word.lower() for word in words)
    if style is NamingStyle.KEBAB:
        return "-".join(word.lower() for word in words)
    if style is NamingStyle.PASCAL:
        return "".join(word[:1].upper() + word[1:].lower() for word in words)
    return words[0].lower() + "".join(word[:1].upper() + word[1:].lower() for word in words[1:])


def _split_words(name: str) -> list[str]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    return [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]


__all__ = ["NamingStyle", "transform"]
