---
name: plugin-contract
description: Контракты generator и FormatPlugin Eggpipe — публичный API v2.0, decorator API, версии и чек-лист
---

# Контракты плагинов Eggpipe

Источник истины: актуальное ТЗ v2.0 §6 и System Design §2.

## Публичный API

Из `eggpipe.__init__` экспортируются стабильные контракты:

`GeneratorPlugin`, `GeneratorInput`, `GenerationResult`, `Artifact`, `GenerationContext`,
`FormatInfo`, `FormatSchema`, `ImportedFile`, `SourceModel`, `ModelSlice`, `Entity`,
`EntityIdentity`, `FieldIdentity`, `FieldDef`, `EnumDef`, `CustomType`, `GeneratorConfig`,
`NamingStyle`, `transform`, `Diagnostic`, `EngineReport`, `Engine`, `AppConfig`,
`GeneratorRules`, `GeneratorRulesLoader`, `FormatRegistry`, `FormatPlugin`,
`EntityModelFormat`, `MergePolicy`, `generator`, `Provenance`, `git_provenance`, `UNSET`,
`PRIMITIVE_TYPES`, `Constraints` и базовые исключения.

Всё из `core.*` и `engine.*` — внутреннее. Пакет поставляет `py.typed`; публичные имена
входят в `__all__`.

## Основной API: `@generator`

```python
from eggpipe import Artifact, GenerationContext, GeneratorConfig, ModelSlice, generator


@generator(id="my-generator", input_formats={"entity-model"})
def my_generator(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    return [Artifact(path="my_output.py", content="...")]
```

Правила:

- `input_formats` обязателен: `None` — любой формат, `set()` — ни один, набор — форматы
  и их наследники.
- `id` опционален; по умолчанию имя функции с `_` → `-`.
- `name` опционален; по умолчанию human-readable имя.
- `api_version` опционален, default `"1"`.
- Аргументы инжектятся по аннотациям: `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
  Другие аннотации — MG302.
- Возврат: `GenerationResult`, `Artifact`, `list[Artifact]`, `tuple[Artifact, ...]`.
- Entry point указывает на декорированную функцию.
- Классовый `GeneratorPlugin` остаётся advanced-API.

## Классовый GeneratorPlugin

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
            artifacts=[Artifact(path="my_output.py", content="...")],
        )
```

Правила:

- `input_formats` обязателен. Отсутствие поля — MG301.
- `id` совпадает с entry point id и pattern `^[a-z][a-z0-9-]*$`.
- `generate()` получает `ModelSlice` + `GenerationContext` + `GeneratorConfig`;
  `AppConfig` не передаётся.
- Входы immutable: не мутируй `input`, `input.model`, `input.context`.
- Плагин **не пишет файлы** сам. Только возвращает `Artifact`.
- `Artifact.path` — относительный POSIX-путь; `content` — `str`, UTF-8, LF, без BOM.
- Ошибки и предупреждения — структурированные `Diagnostic`, не строки.
- Если `errors` непустой, артефакты этого генератора отбрасываются; остальные генераторы
  продолжают работу.
- Исключения ловит ядро и превращает в ошибку генератора (exit 1).
- `validate_config()` вызывается до `generate()`; экземпляр создаётся один раз на запуск.
- `GenerationContext.formats` — `frozenset[FormatInfo]`; формат сущности — `Entity.format`.

## FormatPlugin

```python
from typing import ClassVar, Literal

from eggpipe import EntityModelFormat, FormatSchema


class MyFormat(EntityModelFormat):
    api_version: ClassVar[Literal["1"]] = "1"
    format_names: ClassVar[list[str]] = ["sql-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}
    primitive_types: ClassVar[set[str]] = {...}
    schemas: ClassVar[dict[str, FormatSchema]] = {...}

    def parse_extensions(self, document, raw) -> None: ...
    def validate_extensions(self, document) -> list[Diagnostic]: ...
```

Правила:

- `format_names` совпадает с `format` в заголовке документа.
- `entity-model` зарезервирован; переопределять его нельзя.
- Формат, расширяющий `entity-model`, наследует `EntityModelFormat`, переопределяет
  ClassVar-метаданные (`format_names`, `extends`, `base_versions`, `supported_versions`,
  `primitive_types`, `schemas`) и hooks `parse_extensions`/`validate_extensions`;
  `parse`/`validate` не переопределяет.
- `version` в YAML опционален: нет версии — последняя из `supported_versions`.
- Версии форматов независимы; `base_versions[B_version] = A_version`.
- `schemas[version]` содержит `layer_entity`/`full_entity`; ключи совпадают с версиями.
- `full_entity` расширения наследует `full_entity` базовой версии.
- `primitive_types` расширения — надмножество примитивов базы.
- В одном запуске допускаются разные форматы; несовместимый генератор — MG033.
- Дополнительные поля могут быть first-class полями Pydantic-модели; `metadata` —
  extension point.
- Неизвестная версия формата — MG008; ошибка наследования/схем — MG034.

## Versioning

- `api_version = "1"` — первый стабильный контракт.
- Несовместимый плагин не ломает запуск, если не выбран; показывается как incompatible.
- Явно выбранный несовместимый плагин — exit 2.
- MG033/MG034/MG301/MG302 — config/plugin errors, exit 2.
- Политика deprecation применяется после первого публичного релиза.

## Чек-лист ревью

### Generator

- [ ] `api_version`, `id`, `name`, `input_formats` заданы как `ClassVar`.
- [ ] `input_formats` обязателен: `None` — любой, `set()` — ни один.
- [ ] Entry point совпадает с `id`; `id` соответствует pattern.
- [ ] Для decorator API аннотации только `ModelSlice`/`GenerationContext`/`GeneratorConfig`.
- [ ] Return type — `GenerationResult`, `Artifact`, `list[Artifact]` или `tuple[Artifact, ...]`.
- [ ] Нет записи в файловую систему и нет доступа к `AppConfig`.
- [ ] Вход не мутируется; используются только публичные типы.
- [ ] Пути артефактов относительные, POSIX, без `..` и абсолютных корней.
- [ ] Диагностики структурированы, коды стабильны.
- [ ] Ошибки не роняют другие генераторы.
- [ ] `naming_hint` используется как подсказка; канонические имена не переименовываются.

### Format

- [ ] `api_version`, `format_names`, `extends`, `base_versions`, `supported_versions`,
      `primitive_types`, `schemas` заданы как `ClassVar`.
- [ ] `format_names` совпадает с `format` в заголовке; `entity-model` не переопределён.
- [ ] `version` опционален; latest берётся из `supported_versions`.
- [ ] `base_versions` задаёт зависимость версий; `schemas` содержит layer/full entity.
- [ ] `full_entity` наследует базовую схему; `primitive_types` — надмножество.
- [ ] Ошибки версии — MG008; наследования/схем — MG034; несовместимости — MG033.

### Оба типа

- [ ] Добавлены contract- и golden-тесты для детерминированного вывода.
- [ ] `eggpipe gen list`/`format list` показывают плагин без ошибок.
