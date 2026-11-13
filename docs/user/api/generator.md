# Generator API

## Основной способ: `@generator`

```python
from eggpipe import Artifact, GenerationContext, GeneratorConfig, ModelSlice, generator


@generator(id="my-generator", input_formats={"entity-model"})
def my_generator(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [Artifact(path="user.py", content="...")]
```

Правила:

- `input_formats` обязателен: `None` — любой формат, `set()` — ни один, набор — форматы
  и их наследники.
- `id` опционален; по умолчанию имя функции с `_` → `-`.
- `name` опционален.
- `api_version` по умолчанию `"1"`.
- Аннотации инжектируются: `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
  Неизвестная аннотация — EG302.
- Возврат: `GenerationResult`, `Artifact`, `list[Artifact]`, `tuple[Artifact, ...]`.
- Entry point указывает на декорированную функцию:

```toml
[project.entry-points."eggpipe.generators"]
my-generator = "my_package.plugins:my_generator"
```

## Классовый API

```python
from typing import ClassVar, Literal

from eggpipe import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin


class MyGenerator(GeneratorPlugin):
    api_version: ClassVar[Literal["1"]] = "1"
    id: ClassVar[str] = "my-generator"
    name: ClassVar[str] = "My Generator"
    input_formats: ClassVar[set[str] | None] = {"entity-model"}

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(
            artifacts=[Artifact(path="user.py", content="...")],
        )
```

Классовый API удобен для состояния/конфигурации; `validate_config()` можно переопределить.

## Вход

```python
GeneratorInput(
    model: ModelSlice,              # замкнутый срез
    config: GeneratorConfig,        # блок generators[] из .eggpipe.yaml
    context: GenerationContext,     # variables, imports, sources, formats, run_id
)
```

`GenerationContext.formats` — `frozenset[FormatInfo]`; формат конкретной сущности —
`entity.format` / `entity.format_version`.

## Выход

- `Artifact.path` — относительный POSIX-путь.
- `Artifact.content` — `str`, UTF-8, LF, без BOM.
- Ошибки/warnings — `Diagnostic`.
- Если `errors` непустой, артефакты этого генератора отбрасываются.
- Исключение ловится ядром и превращается в EG300; остальные генераторы продолжаются.

## Совместимость форматов

Ядро проверяет каждую сущность среза против `input_formats` до `validate_config()` и
`generate()`. Несовместимость — EG033, exit 2, pre-flight ошибка всего запуска.

`{"entity-model"}` принимает сам `entity-model` и всех его наследников.
