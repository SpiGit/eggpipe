"""Загрузка YAML в безопасном режиме (YAML 1.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError


class YamlLoadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def load_yaml(path: Path) -> dict[str, Any]:
    """Прочитать один YAML-документ-словарь; duplicate keys — ошибка."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise YamlLoadError("MG000", f"не удалось прочитать файл: {exc}") from exc

    yaml = YAML(typ="safe")
    yaml.allow_duplicate_keys = False
    try:
        documents = list(yaml.load_all(text))
    except DuplicateKeyError as exc:
        raise YamlLoadError("MG000", f"дубликат ключа: {exc}") from exc
    except YAMLError as exc:
        raise YamlLoadError("MG000", f"синтаксис YAML: {exc}") from exc

    if len(documents) != 1:
        raise YamlLoadError(
            "MG000",
            f"ожидался один YAML-документ, найдено: {len(documents)}",
        )
    data = documents[0]
    if not isinstance(data, dict):
        raise YamlLoadError("MG000", "корень документа должен быть словарём")
    return data
