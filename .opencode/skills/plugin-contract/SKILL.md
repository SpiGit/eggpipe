---
name: plugin-contract
description: Контракты GeneratorPlugin и FormatPlugin Eggpipe — публичный API, ограничения и чек-лист реализации
---

# Контракты плагинов

Используй этот skill при разработке, ревью и документировании плагинов генераторов и форматов.
Источник истины: актуальное ТЗ §6 и System Design §2.

## Публичный API

Из `metadata_generator.__init__` экспортируются только:

`GeneratorPlugin`, `GeneratorInput`, `GenerationResult`, `Artifact`, `GenerationContext`,
`ImportedFile`, `SourceModel`, `ModelSlice`, `Entity`, `FieldDef`, `EnumDef`, `CustomType`,
`GeneratorConfig`, `NamingStyle`, `transform`, `Diagnostic`, `EngineReport`, `Engine`,
`AppConfig`, `GeneratorRules`, `GeneratorRulesLoader`, `FormatRegistry` и базовые исключения.

Всё из `core.*` — внутреннее. Пакет поставляет `py.typed`; публичные имена входят в `__all__`.

## GeneratorPlugin

```python
from typing import ClassVar, Literal

from metadata_generator import (
    Artifact,
    GeneratorInput,
    GeneratorPlugin,
    GenerationResult,
)


class MyGenerator(GeneratorPlugin):
    api_version: ClassVar[Literal["1"]] = "1"
    id: ClassVar[str] = "my-generator"
    name: ClassVar[str] = "My Generator"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        return GenerationResult(
            artifacts=[Artifact(path="my_output.py", content="...")],
        )
```

Правила:

- `id` совпадает с entry point id; `name` по умолчанию равен `id`.
- `generate()` получает `ModelSlice` + `GenerationContext` + `GeneratorConfig`; `AppConfig` не передаётся.
- Входы immutable: не мутируй `input`, `input.model`, `input.context`.
- Плагин **не пишет файлы** сам. Только возвращает `Artifact`.
- `Artifact.path` — относительный POSIX-путь; `content` — `str`, UTF-8, LF, без BOM.
- Ошибки и предупреждения — структурированные `Diagnostic`, не строки.
- Если `errors` непустой, артефакты этого генератора отбрасываются; остальные генераторы продолжают работу.
- Исключения ловит ядро и превращает в ошибку генератора (exit 1).
- `validate_config()` вызывается до `generate()`; экземпляр создаётся один раз на запуск.

## FormatPlugin

```python
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

`EntityModelFormat` — база ядра для расширения `entity-model`; входит в публичный API.

Правила:

- `format_names` совпадает с `format` в заголовке документа.
- `entity-model` зарезервирован; переопределять его нельзя.
- Формат, расширяющий `entity-model`, наследует `EntityModelFormat`, переопределяет ClassVar-метаданные
  (`format_names`, `extends`, `base_versions`, `supported_versions`, `primitive_types`, `schemas`)
  и hooks `parse_extensions`/`validate_extensions`; `parse`/`validate` не переопределяет.
- `version` в YAML опционален: нет версии — последняя из `supported_versions`.
- Версии форматов независимы; `base_versions[B_version] = A_version`.
- `schemas[version]` содержит `layer_entity`/`full_entity`.
- В одном запуске допускаются разные форматы; несовместимый генератор — MG033.
- Дополнительные поля могут быть first-class полями Pydantic-модели; `metadata` — extension point.
- Неизвестная версия формата — `MG008`; ошибка наследования/схем — `MG034`.

## Versioning

- `api_version = "1"` — первый стабильный контракт.
- Несовместимый плагин не ломает запуск, если не выбран; показывается как incompatible.
- Явно выбранный несовместимый плагин — exit 2 с понятной ошибкой.
- Политика deprecation применяется после первого публичного релиза.

## Чек-лист ревью

### GeneratorPlugin

- [ ] `api_version`, `id`, `name`, `input_formats` заданы как `ClassVar`.
- [ ] `input_formats` обязателен: `None` — любой, `set()` — ни один.
- [ ] Entry point совпадает с `id`.
- [ ] Нет записи в файловую систему и нет доступа к `AppConfig`.
- [ ] Вход не мутируется; используются только публичные типы.
- [ ] Пути артефактов относительные, POSIX, без `..` и абсолютных корней.
- [ ] Диагностики структурированы, коды стабильны.
- [ ] Ошибки не роняют другие генераторы.
- [ ] `naming_hint` используется как подсказка; канонические имена не переименовываются ядром.

### FormatPlugin

- [ ] `api_version`, `format_names`, `extends`, `base_versions`, `supported_versions`,
      `primitive_types`, `schemas` заданы как `ClassVar`.
- [ ] `format_names` совпадает с `format` в заголовке; `entity-model` не переопределён.
- [ ] `version` опционален; latest берётся из `supported_versions`.
- [ ] `base_versions` задаёт зависимость версий; `schemas` содержит layer/full entity.
- [ ] Ошибки версии — `MG008`; наследования/схем — `MG034`; несовместимости генератора — `MG033`.

### Оба типа

- [ ] Добавлены contract- и golden-тесты для детерминированного вывода.
