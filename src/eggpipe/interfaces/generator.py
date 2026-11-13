"""Контракты генераторов."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Literal, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, Field

from eggpipe.config.generator_rules import GeneratorConfig
from eggpipe.core.model import FormatInfo, ModelSlice
from eggpipe.core.naming import NamingStyle
from eggpipe.interfaces.diagnostics import Diagnostic
from eggpipe.utils.exceptions import PluginContractError


class ImportedFile(BaseModel):
    name: str
    path: Path
    content: bytes

    model_config = ConfigDict(extra="forbid", frozen=True)

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding)


class GenerationContext(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)
    naming_hint: NamingStyle | None = None
    imports: dict[str, ImportedFile] = Field(default_factory=dict)
    sources: list[Path] = Field(default_factory=list)
    formats: frozenset[FormatInfo] = frozenset()
    run_id: str
    config_dir: Path

    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(BaseModel):
    path: str
    content: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationResult(BaseModel):
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[Diagnostic] = Field(default_factory=list)
    errors: list[Diagnostic] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def success(self) -> bool:
        return not self.errors


class GeneratorInput(BaseModel):
    model: ModelSlice
    config: GeneratorConfig
    context: GenerationContext

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneratorPlugin(ABC):
    api_version: ClassVar[Literal["1"]] = "1"
    id: ClassVar[str]
    name: ClassVar[str] = ""
    input_formats: ClassVar[set[str] | None]

    @abstractmethod
    def generate(self, input: GeneratorInput) -> GenerationResult:
        """Сгенерировать артефакты, не записывая файлы."""

    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        return []


_INJECTABLE = (ModelSlice, GenerationContext, GeneratorConfig)


def generator(
    *,
    id: str | None = None,
    name: str | None = None,
    input_formats: set[str] | None,
    api_version: Literal["1"] = "1",
) -> Callable[[Callable[..., Any]], type[GeneratorPlugin]]:
    """Объявить генератор функцией; создаёт класс-адаптер GeneratorPlugin."""
    if input_formats is not None and (
        not isinstance(input_formats, set)
        or any(not isinstance(item, str) or not item for item in input_formats)
    ):
        raise PluginContractError("MG301", "input_formats должен быть set[str] или None")
    formats = set(input_formats) if input_formats is not None else None

    def decorate(function: Callable[..., Any]) -> type[GeneratorPlugin]:
        generator_id = id or function.__name__.lower().replace("_", "-")
        if not re.fullmatch(r"^[a-z][a-z0-9-]*$", generator_id):
            raise PluginContractError("MG301", f"некорректный id генератора: {generator_id!r}")
        generator_name = name or function.__name__.replace("_", " ").title()
        adapter_version = api_version
        adapter_formats = formats

        class Adapter(GeneratorPlugin):
            api_version: ClassVar[Literal["1"]] = adapter_version
            id: ClassVar[str] = generator_id
            name: ClassVar[str] = generator_name
            input_formats: ClassVar[set[str] | None] = adapter_formats
            _function: ClassVar[Callable[..., Any]] = staticmethod(function)

            def generate(self, input: GeneratorInput) -> GenerationResult:
                value = _invoke_generator(type(self)._function, input)
                return _normalize_generation_result(value)

        Adapter.__name__ = f"{function.__name__}_generator"
        Adapter.__qualname__ = Adapter.__name__
        return Adapter

    return decorate


def validate_generator_contract(plugin: GeneratorPlugin) -> None:
    plugin_type = type(plugin)
    plugin_id = getattr(plugin_type, "id", None)
    if not isinstance(plugin_id, str) or not re.fullmatch(r"^[a-z][a-z0-9-]*$", plugin_id):
        raise PluginContractError("MG301", f"некорректный id генератора: {plugin_id!r}")
    if not hasattr(plugin_type, "input_formats"):
        raise PluginContractError("MG301", "input_formats обязателен")
    formats = plugin_type.input_formats
    if formats is not None and (
        not isinstance(formats, set)
        or any(not isinstance(item, str) or not item for item in formats)
    ):
        raise PluginContractError("MG301", "input_formats должен быть set[str] или None")
    function = getattr(plugin_type, "_function", None)
    if function is not None:
        validate_generator_function(function)


def validate_generator_function(function: Callable[..., Any]) -> None:
    try:
        hints = get_type_hints(function)
        signature = inspect.signature(function)
    except (NameError, TypeError) as exc:
        raise PluginContractError("MG301", f"не удалось прочитать сигнатуру: {exc}") from exc

    injected: set[type[Any]] = set()
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            raise PluginContractError("MG301", "*args/**kwargs не поддерживаются")
        hint = hints.get(parameter.name)
        if hint is None:
            raise PluginContractError(
                "MG301",
                f"у параметра {parameter.name} нет аннотации",
            )
        if hint not in _INJECTABLE:
            raise PluginContractError(
                "MG302",
                f"неизвестный инжектируемый параметр {parameter.name}: {hint!r}",
            )
        if hint in injected:
            raise PluginContractError("MG301", f"повторная инъекция {hint.__name__}")
        injected.add(hint)

    result_hint = hints.get("return")
    if not _is_valid_return_hint(result_hint):
        raise PluginContractError("MG301", f"недопустимый return type: {result_hint!r}")


def _invoke_generator(function: Callable[..., Any], input: GeneratorInput) -> Any:
    hints = get_type_hints(function)
    values = {
        ModelSlice: input.model,
        GenerationContext: input.context,
        GeneratorConfig: input.config,
    }
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for parameter in inspect.signature(function).parameters.values():
        hint = hints[parameter.name]
        value = values[hint]
        if parameter.kind is parameter.KEYWORD_ONLY:
            kwargs[parameter.name] = value
        else:
            args.append(value)
    return function(*args, **kwargs)


def _normalize_generation_result(value: Any) -> GenerationResult:
    if isinstance(value, GenerationResult):
        return value
    if isinstance(value, Artifact):
        return GenerationResult(artifacts=[value])
    if isinstance(value, (list, tuple)) and all(isinstance(item, Artifact) for item in value):
        return GenerationResult(artifacts=list(value))
    raise PluginContractError(
        "MG301",
        f"недопустимый return type: {type(value).__name__}",
    )


def _is_valid_return_hint(hint: object) -> bool:
    if hint in (GenerationResult, Artifact):
        return True
    if get_origin(hint) not in (list, tuple):
        return False
    args = get_args(hint)
    return bool(args) and args[0] is Artifact


__all__ = [
    "Artifact",
    "GenerationContext",
    "GenerationResult",
    "GeneratorInput",
    "GeneratorPlugin",
    "ImportedFile",
    "generator",
    "validate_generator_contract",
    "validate_generator_function",
]
