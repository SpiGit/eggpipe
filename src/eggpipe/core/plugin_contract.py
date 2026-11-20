"""Shared plugin contract helpers: callable locations and hint texts.

The module is internal: ``interfaces`` and ``engine`` both need the same
location format and the same hints, so they live here instead of being
imported from a private name in another layer.
"""

from __future__ import annotations

from typing import Any

INJECTABLE_PARAMETER_HINT = "ModelSlice, GenerationContext or GeneratorConfig"
RETURN_TYPE_HINT = (
    "expected return type: GenerationResult, Artifact, list[Artifact] or tuple[Artifact, ...]"
)
INPUT_FORMATS_HINT = (
    "declare input_formats = {'entity-model'} or None (None accepts every format), "
    "or use @generator(input_formats=...)"
)


def callable_location(owner: Any) -> str:
    """Return ``module:qualname`` for a class or function."""
    module = getattr(owner, "__module__", None) or "unknown module"
    qualname = getattr(owner, "__qualname__", None) or getattr(owner, "__name__", None)
    if not isinstance(qualname, str) or not qualname:
        return str(module)
    return f"{module}:{qualname}"


def describe_generator_location(plugin: Any) -> str:
    """Return the module and qualified name of a generator class or decorated function."""
    plugin_type = type(plugin)
    function = getattr(plugin_type, "_function", None)
    return callable_location(function if function is not None else plugin_type)


__all__ = [
    "INJECTABLE_PARAMETER_HINT",
    "INPUT_FORMATS_HINT",
    "RETURN_TYPE_HINT",
    "callable_location",
    "describe_generator_location",
]
