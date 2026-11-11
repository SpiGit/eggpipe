---
name: plugin-contract
description: Контракты GeneratorPlugin и FormatPlugin metadata-generator — публичный API, ограничения и чек-лист реализации
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
    primitive_types: ClassVar[set[str]] = {...}

    def parse_extensions(self, document, raw) -> None: ...
    def validate_extensions(self, document) -> list[Diagnostic]: ...
```

`EntityModelFormat` — база ядра для расширения `entity-model`.

Известный дефект текущего контракта: §6.3 требует наследовать `EntityModelFormat`, но §6.2 не
включает его в публичный экспорт. До исправления в следующей версии ТЗ не импортируй внутренние
модули и не добавляй собственный обходной API; зафиксируй дефект в отчёте.

Правила:

- `format_names` совпадает с `format` в заголовке документа.
- `entity-model` зарезервирован; переопределять его нельзя.
- Формат, расширяющий `entity-model`, наследует `EntityModelFormat`, переопределяет ClassVar-метаданные
  формата (`format_names`, `supported_versions`, `primitive_types`) и hooks
  `parse_extensions`/`validate_extensions`; `parse`/`validate` не переопределяет.
- Дополнительные поля складываются в `metadata[<format>]`, а не в произвольные ключи.
- Неизвестная версия формата — `MG008`.
- Один запуск — один формат; смешивание — `MG007`.

## Versioning

- `api_version` повышается только при breaking change контракта.
- Несовместимый плагин не ломает запуск, если не выбран; показывается как incompatible.
- Явно выбранный несовместимый плагин — exit 2 с понятной ошибкой.
- Deprecation: минимум один minor-релиз с Warning, затем удаление.

## Чек-лист ревью

### GeneratorPlugin

- [ ] `api_version`, `id`, `name` заданы как `ClassVar`.
- [ ] Entry point совпадает с `id`.
- [ ] Нет записи в файловую систему и нет доступа к `AppConfig`.
- [ ] Вход не мутируется; используются только публичные типы.
- [ ] Пути артефактов относительные, POSIX, без `..` и абсолютных корней.
- [ ] Диагностики структурированы, коды стабильны.
- [ ] Ошибки не роняют другие генераторы.
- [ ] `naming_hint` используется как подсказка; канонические имена не переименовываются ядром.

### FormatPlugin

- [ ] `api_version`, `format_names`, `supported_versions`, `primitive_types` заданы как `ClassVar`.
- [ ] `format_names` совпадает с `format` в заголовке; `entity-model` не переопределён.
- [ ] Наследование от `EntityModelFormat` не требует импорта внутренних модулей (см. известный дефект).
- [ ] Дополнительные поля лежат в `metadata[<format>]`.
- [ ] Ошибки версии/смешивания форматов используют `MG008`/`MG007`.

### Оба типа

- [ ] Добавлены contract- и golden-тесты для детерминированного вывода.
