# ADR-0005: Library API и границы публичного контракта

- **Статус:** принято
- **Дата:** 2026-11-11
- **Связанные документы:** [ТЗ v1.2 §6.2, §11](../requirements/v1.2.md), [System Design §2.8](../system-design/index.md)

---

## 1. Контекст

`metadata-generator` используется и как CLI, и как библиотека. Плагины и встраивание в другие
приложения требуют стабильного API без глобальных side effects. Внутренние модели и механизмы
композиции не должны становиться частью контракта случайно.

## 2. Решение

- Стабильный публичный API — закрытый список:
  `GeneratorPlugin`, `GeneratorInput`, `GenerationResult`, `Artifact`, `GenerationContext`,
  `ImportedFile`, `SourceModel`, `ModelSlice`, `Entity`, `FieldDef`, `EnumDef`, `CustomType`,
  `GeneratorConfig`, `NamingStyle`, `transform`, `Diagnostic`, `EngineReport`, `Engine`,
  `AppConfig`, `GeneratorRules`, `GeneratorRulesLoader`, `FormatRegistry`, `FormatPlugin`,
  `EntityModelFormat`, `UNSET`, `PRIMITIVE_TYPES`, `Constraints` и базовые исключения.
- Пакет поставляет `py.typed`. `__all__` может содержать дополнительные convenience-имена;
  гарантия стабильности распространяется только на список выше. Расширение списка
  (`UNSET`, `FormatPlugin`, `EntityModelFormat`, `PRIMITIVE_TYPES`) фиксируется в ТЗ v1.3.
- Модули `core.*`, внутренние `engine.*`, `engine.artifact_writer`, `engine.plugin_loader`
  не являются публичным контрактом. `engine/format_registry.py` публичен только в части
  `FormatRegistry`.
- `Engine` — библиотечный фасад:
  - `build()` — parsing/composition/validation/generation/planning **без записи**;
  - `generate()` — `build()` + запись артефактов;
  - `check()` — проверка актуальности без записи; drift → `success=False`, `exit_code=1`;
  - `Engine` не вызывает `sys.exit`, не настраивает root-logger и не меняет глобальное состояние.
- Реестры можно инжектировать: `generators` и `formats`; `config_dir`, `source_paths`
  и `variables` — явные параметры конструктора.
- Config/usage-ошибки выбрасываются исключениями (`ConfigValidationError`, `LockError`,
  `ManifestError`), а не кодируются в отчёте. `DocumentError` — ошибка парсинга: она
  агрегируется в `EngineReport` с `exit_code=1`.
- Ошибки генерации агрегируются в `EngineReport`: `success`, `exit_code`, `diagnostics`,
  `generators`, `artifacts`, `timings`, `run_id`, `report_version`.
- Входы плагинов immutable: `GeneratorInput`, `ModelSlice`, `GenerationContext` frozen;
  `AppConfig` плагину не передаётся.
- Плагины возвращают артефакты и структурированные `Diagnostic`, не пишут файлы сами.
- `api_version` plugin API повышается только при breaking change; deprecation — минимум один
  minor-релиз с Warning.
- CLI отвечает за логирование, rich-вывод, exit codes и обработку Ctrl+C; библиотека — нет.

## 3. Последствия

- Пользователи могут встраивать `Engine` в скрипты и тесты без побочных эффектов.
- Плагины тестируются через `GeneratorInput`/`GenerationResult` и reference-плагин.
- Внутренние классы можно рефакторить, не ломая публичный API.
- Публичный API расширяется осторожно: новое имя попадает в `__all__` и документируется.

## 4. Альтернативы

- Сделать публичными все модули — отклонено: невозможно поддерживать стабильность.
- Вернуть exit code из `Engine.generate()` вместо исключений — отклонено: смешивает библиотеку
  и CLI.
- Передавать `AppConfig` плагинам — отклонено: технические настройки не часть plugin contract.
