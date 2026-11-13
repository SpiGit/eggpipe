# ADR-0011: Публичный API v2.1 и идентичность Eggpipe

- **Статус:** принято
- **Дата:** 2026-11-13
- **Связанные документы:** [ТЗ v2.1 §6, §11](../requirements/v2.1.md), [ADR-0005](./0005-library-api.md), [ADR-0009](./0009-global-manifest-ownership.md), [ADR-0010](./0010-decorator-generator-api.md)

---

## 1. Контекст

К v2.1 проект прошёл три связанных изменения, которые не были оформлены отдельным ADR:

1. идентичность проекта изменилась: `metadata_generator`/`mg`/`.mg.yaml`/`.mg/` →
   `eggpipe`/`eggpipe`/`.eggpipe.yaml`/`.eggpipe/`;
2. публичный API расширился контрактами форматов, model units, decorator API и provenance;
3. JSON-отчёт и manifest получили собственные версии (`report_version`, `manifest_version`).

Без ADR эти решения существовали только в ТЗ и коде. ADR-0005 описывает раннюю версию
библиотечного API, ADR-0009 — ownership/manifest, ADR-0010 — decorator API, но не
фиксируют итоговый состав публичного API и границу «стабильное/внутреннее».

## 2. Решение

### 2.1. Идентичность

- Имя проекта: **Eggpipe**; CLI: `eggpipe`.
- Python package/import: `eggpipe`; entry points: `eggpipe.generators`, `eggpipe.formats`.
- Конфиг: только `.eggpipe.yaml`; state: `.eggpipe/`; manifest `.eggpipe/manifest.json`;
  lock `.eggpipe/lock`.
- Env prefix: `EGGPIPE_`.
- Старые имена (`metadata_generator`, `mg`, `.mg.yaml`, `.mg/`) остаются только
  в исторических ТЗ и ADR; обратная совместимость не поддерживается.

### 2.2. Стабильный публичный API

Из `eggpipe.__init__` стабильно экспортируются:

`GeneratorPlugin`, `GeneratorInput`, `GenerationResult`, `Artifact`, `GenerationContext`,
`FormatInfo`, `FormatSchema`, `ImportedFile`, `SourceModel`, `ModelSlice`, `Entity`,
`EntityIdentity`, `FieldIdentity`, `FieldDef`, `EnumDef`, `CustomType`, `GeneratorConfig`,
`NamingStyle`, `transform`, `Diagnostic`, `EngineReport`, `Engine`, `AppConfig`,
`GeneratorRules`, `GeneratorRulesLoader`, `FormatRegistry`, `FormatPlugin`,
`EntityModelFormat`, `MergePolicy`, `generator`, `Provenance`, `git_provenance`, `UNSET`,
`PRIMITIVE_TYPES`, `Constraints` и базовые исключения.

Всё из `core.*`, `engine.*`, `utils.*` — внутренняя реализация и может меняться между
minor-версиями пакета. Пакет поставляет `py.typed`; публичные имена входят в `__all__`.

### 2.3. Версионирование контрактов

| Контракт | Поле/механизм | Политика |
|----------|---------------|----------|
| Plugin API | `api_version = "1"` | ломающее изменение — новая версия API |
| Format schema | `FormatPlugin.schemas[version]` | версии формата независимы |
| Manifest | `manifest_version` | v1 не поддерживается |
| JSON report | `report_version` | `2` в v2.1; enum действий фиксирован |
| Пакет | SemVer | до 1.0 minor может ломать |

### 2.4. Provenance и ошибки

- `Provenance`/`git_provenance` входят в стабильный API.
- Базовая ошибка библиотеки — `EggpipeError`; ошибки парсинга/конфигурации остаются
  доменными исключениями, а ошибки генераторов агрегируются в `Diagnostic`.
- `PluginContractError` и `FormatInheritanceError` несут стабильные коды MG301/MG302/MG034.

## 3. Последствия

- Новые публичные имена требуют обновления `__all__`, `py.typed` и этого ADR.
- Внутренние модули можно рефакторить без ADR, если не меняется публичный API.
- Переименование пакета/CLI/state больше не является открытым вопросом.
- JSON-отчёт и manifest версионируются независимо от версии пакета.

## 4. Альтернативы

- Сохранить старые имена как алиасы — отклонено до первого релиза: лишняя сложность.
- Считать публичным весь `eggpipe.*` — отклонено: невозможно развивать внутренности.
- Привязать `report_version`/`manifest_version` к версии пакета — отклонено:
  это разные контракты с разной скоростью изменений.
