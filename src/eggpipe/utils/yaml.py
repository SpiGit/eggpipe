"""Safe YAML loading (YAML 1.2)."""

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
    """Read a single YAML mapping document; duplicate keys are an error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise YamlLoadError("EG000", f"failed to read file: {exc}") from exc

    yaml = YAML(typ="safe")
    yaml.allow_duplicate_keys = False
    try:
        documents = list(yaml.load_all(text))
    except DuplicateKeyError as exc:
        raise YamlLoadError("EG000", f"duplicate key: {exc}") from exc
    except YAMLError as exc:
        raise YamlLoadError("EG000", f"YAML syntax error: {exc}") from exc

    if len(documents) != 1:
        raise YamlLoadError(
            "EG000",
            f"expected one YAML document, found {len(documents)}",
        )
    data = documents[0]
    if not isinstance(data, dict):
        raise YamlLoadError("EG000", "document root must be a mapping")
    return data
