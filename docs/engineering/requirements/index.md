# Технические требования

| Версия | Дата | Статус | Файл |
|--------|------|--------|------|
| 2.2 | 2026-11-13 | **Актуальная** | [v2.2](./v2.2.md) |
| 2.1 | 2026-11-13 | Замещена | [v2.1](./v2.1.md) |
| 2.0 | 2026-11-12 | Замещена | [v2.0](./v2.0.md) |
| 1.4 | 2026-11-12 | Замещена | [v1.4](./v1.4.md) |
| 1.3 | 2026-11-11 | Замещена | [v1.3](./v1.3.md) |
| 1.2 | 2026-11-11 | Замещена | [v1.2](./v1.2.md) |
| 1.1 | 2026-11-10 | Замещена | [v1.1](./v1.1.md) |
| 1.0 | 2025-11-03 | Замещена | [v1.0](./v1.0.md) |

## Структура требований

- [v2.2](./v2.2.md) — рабочая версия (English-only, EG-коды, ProjectConfig)
- [v2.1](./v2.1.md) — предыдущая рабочая версия (уточнения контрактов)
- [v2.0](./v2.0.md) — предыдущая рабочая версия (Eggpipe, breaking changes)
- [v1.4](./v1.4.md) — предыдущая рабочая версия (история)
- [v1.3](./v1.3.md) — предыдущая рабочая версия (история)
- [v1.2](./v1.2.md) — предыдущая рабочая версия (история)
- [v1.1](./v1.1.md) — предыдущая рабочая версия (история)
- [v1.0](./v1.0.md) — первая рабочая версия (история)

## Changelog

### v2.2 (2026-11-13)

Контрактное обновление перед публичным релизом:

- English-only source code, comments, docstrings, CLI help и diagnostics;
- диагностические коды `MGxxx` → `EGxxx`, номера сохранены;
- `GeneratorRules`/`GeneratorRulesLoader` → `ProjectConfig`/`ProjectConfigLoader`;
- удалён `InputSlice`, используется `InputSelection`;
- удалены `CompositionResult.format`/`version`;
- унифицированы ignore-константы, `WIN_RESERVED` переименован;
- translation memory сохранён в `docs/engineering/i18n/`;
- ADR-0012 (English-only) и ADR-0013 (EG-коды).

### v2.1 (2026-11-13)

Уточнение контрактов без изменения архитектуры:

- JSON-отчёт: каноническое `artifacts[].action` и enum значений; `generators[].status`;
- `timings` — обязательные фазы с допустимым `0`;
- MG014 ограничен `file-per-model`;
- `--plugin` зафиксирован как поставленный dev-only флаг;
- `model schema` без `--format` печатает `ModelDocument`;
- MG001 зарезервирован, неизвестный тип — MG004;
- дерево модулей §11.1 синхронизировано с реализацией;
- уточнены термины, флаги, discovery/MG023 и watch exit code.

### v2.0 (2026-11-12)

Мажорная версия: Eggpipe и breaking changes.

- проект переименован в **Eggpipe**;
- CLI `mg` → `eggpipe`;
- конфиг `.mg.yaml` → `.eggpipe.yaml`;
- state `.mg/` → `.eggpipe/`;
- package/import `metadata_generator` → `eggpipe`;
- entry points `metadata_generator.*` → `eggpipe.*`;
- manifest `.eggpipe/manifest.json`, lock `.eggpipe/lock`;
- решения v1.4 (форматы, версии, model units, ресурсы, decorator API, global manifest)
  вошли без изменения смысла;
- CLI/UX, diagnostics и JSON-отчёт v2 зафиксированы;
- версия пакета остаётся 0.x; это версия ТЗ.

### v1.4 (2026-11-12)

Новое видение форматов и структуры источников:

- формат-плагины могут расширять формат через одиночное наследование `extends`;
- версии форматов независимы; `base_versions` задаёт зависимость, `version` опционален (latest);
- `schemas[version]` содержит `layer_entity` для отдельного слоя и `full_entity` для итоговой сущности;
- генератор объявляет `input_formats`; совместимость учитывает наследников;
- `@generator` — основной decorator API; классовый `GeneratorPlugin` — advanced;
- в одном запуске допускаются модели разных форматов; несовместимый генератор — MG033,
  pre-flight ошибка всего запуска (exit 2);
- модель = одна сущность; раскладки `monolith`, `file-per-model`, `directory-per-model`;
- `directory-per-model`: явные `model_dirs`, `files`, `resources`, слои форматов;
- ресурсы: top-level `resources` + `models.<dir>.resources`; alias, glob, границы;
- layer merge аддитивный, без переопределений; `metadata` мержится;
- list merge: `KEYED` для `fields`, `APPEND` для `types`/`enums`, `UNION`/`ERROR` для кастомных списков;
- `Entity.format`/`format_version`/`layer_sources`, `FieldDef.source`,
  `GenerationContext.formats`; `format`/`format_version` удалены;
- `layout` обязателен; legacy discovery удалён;
- manifest v2: глобальный `.mg/manifest.json`, `formats` вместо `format`, v1 не поддерживается;
- `mg clean` работает по глобальному manifest, без `.mg.yaml` и плагинов;
- `--force` не отбирает файлы у другого generator/location;
- `input_formats` обязателен для каждого генератора;
- новые диагностики MG027, MG029, MG031–MG038, MG051, MG052, MG301, MG302;
- JSON-отчёт v2: formats, input_formats, плоские artifacts, manifest locations, stale_locations;
- `diagnostics.ignore`/`--ignore` игнорируют только warnings.

### v1.3 (2026-11-11)

Приведение ТЗ в соответствие с реализацией v0.1–v0.3:

- зарегистрированы `MG030` (fallback/неподдерживаемый режим) и `MG300` (генератор/запись/drift);
- таблица диапазонов `MGxxx` приведена к фактическим кодам;
- публичный API дополнен `UNSET`, `FormatPlugin`, `EntityModelFormat`, `PRIMITIVE_TYPES`,
  `Constraints`; добавлен `Engine.check()`;
- `Entity.source` для provenance;
- `cleanup: prompt` — fallback `off` + MG030 до полноценного tty-подтверждения;
- `mg model schema` и `mg config schema`.

### v1.2 (2026-11-11)

Результат ревью v1.1 и внесения P0-исправлений (см. [review](../reviews/2026-11-10-project-review.md)). Ключевые изменения:

- **Модель данных:**
  - Явные этапы `ModelDocument` → `SourceModel` → `ModelSlice`; `imports` поднимаются на уровень документа
  - `metadata` доступен у entity/field/enum/type/source; `constraints` описаны у поля
  - `default` использует sentinel `UNSET`: отсутствие ключа отличается от `default: null`
  - Null-matrix расширена до 12 комбинаций; `required=false, nullable=false, default` не задан — валидное состояние
  - `extends` получил явную форму `{import, entity}`; разрешён только внутри import-closure своего документа
  - Удалён `required_by_default`
- **Форматы:**
  - `format` и `version` обязательны; неизвестный формат/версия — ошибка без «тихого» default
  - Один запуск — один формат; импортируемые документы обязаны иметь тот же формат
  - Формат-плагин объявляет `primitive_types`, `supported_versions` и хуки через `EntityModelFormat`
- **Композиция и срезы:**
  - Discovery-правила для каталогов `sources`; project-root boundary для импортов + `--allow-outside-imports`
  - Финальный срез = пересечение `sources[].input` ∩ `generators[].input` + транзитивное замыкание по enums/types
  - Дубликаты resolved-путей обрабатываются один раз (Warning MG024)
- **Плагины:**
  - Структурированные `Diagnostic` вместо строк; `ClassVar`-контракты; ошибки генератора отбрасывают его артефакты
  - Публичный API расширен: `Engine`, `EngineReport`, `Diagnostic`, `ModelSlice`, `FieldDef`, `EnumDef`, `AppConfig`, `GeneratorRulesLoader`, `FormatRegistry`
  - `Field`/`Enum` переименованы в `FieldDef`/`EnumDef`
- **Запись артефактов:**
  - Полные правила валидации путей (POSIX, NFC, reserved names, symlink, case-collisions)
  - Ownership: перезапись/удаление только owned-файлов; для чужих — `--force`
  - Per-generator manifest `output_dir/.mg/manifests/<id>.json`
  - `cleanup` по умолчанию `off`; удаляются только неизменённые owned-файлы
  - Lock `.mg/lock`; `--plan`, `--check` без побочных эффектов
- **CLI:**
  - Новые команды: `mg clean`, `mg gen info`, `mg format list`
  - Новые флаги: `--plan`, `--check`, `--force`, `--yes`, `--include-disabled`, `--allow-outside-imports`
  - `--format` переименован в `--output-format`; exit code 130 при Ctrl+C
- **Парсинг:** `ruamel.yaml` (YAML 1.2), duplicate keys — ошибка
- **Качество:** расширены тесты (contract/security/determinism/cleanup/concurrency), benchmark-методика, CI-матрица 3.11/3.12

### v1.1 (2026-11-10)

Результат общесистемного ревью v1.0. Ключевые изменения:

- **Модель:**
  - Сущности изолированы: базовая модель не знает отношений между сущностями
  - Заголовок документа сокращён до `format` + `version` (`extends` удалён — формат задаёт формат-плагин)
  - `updated_at`/`version` перенесены с уровня документа на уровень **entity**
  - `default` — только скаляр, `auto` убрано из базовой схемы (автогенерация — зона формата/генератора)
  - `nullable` явно в схеме, `default: false`; определена null-матрица (§3.6: 4 валидных состояния + запрещённые комбинации)
- **Форматы:**
  - Формат определяет плагин; реестр форматов; встроен только `entity-model`
  - Введён второй тип плагина — формат-плагин (entry points `metadata_generator.formats`)
- **Композиция:**
  - Семантика merge зафиксирована в [ADR-0001](../adr/0001-composition-merge-semantics.md): merge только по явным связям, аддитивный, детерминированный, конфликты имён — ошибки
  - Entity extends: замещение поля целиком, позиции parent-полей сохраняются
- **Плагины:**
  - Вход генератора — цельный срез модели (GeneratorInput), выход — артефакты с относительными путями (имена файлов — зона плагина)
  - `app_config` передано плагину уже не будет — публичный контракт чистый
  - `api_version` + versioning публичного API ядра
- **Запись артефактов:**
  - `on_conflict: overwrite | skip | error`
  - Атомарная запись (staging → move)
  - Манифест `.mg-manifest.json` + cleanup осиротевших файлов (`off | prompt | enabled`)
- **CLI:**
  - Единый подкомандный стиль: `mg config show`, `mg model validate`, `mg gen list`
  - `--strict` (warnings → errors), `--var KEY=VALUE` (CLI > variables в .mg.yaml, доставка через `GenerationContext`)
  - Зафиксированы exit-коды (0/1/2) и поведение при ошибке генератора (остальные продолжаются)
- **Локальные плагины:** только editable install; `sys.path`-хаки и `plugins_dir` убраны
- **Naming:** ядро предоставляет утилиты и подсказку `naming_convention`; переименование модели — всегда решение плагина
- **Roadmap v0.1 → v0.2 → v0.3** (§13): ядро → композиция → формат-плагины/watch/json

Подробная критика и решения — в `.session-context.md` (сессия 2026-11-10).

### v1.0 (2025-11-03)
- Начальная рабочая версия
- Определена структура документа модели:
  - `format` — тип документа (для парсера), **не привязан к генераторам**
  - `extends` — наследование типов
  - `version` — версия схемы формата
  - `updated_at` — дата изменения в ISO 8601
- Универсальная базовая схема `entity-model`:
  - entities, enums, types (без SQL-специфики)
  - SQL/API/другие концепции — через наследование в пользовательских типах
- **Композиция данных (Composition)**:
  - 3 варианта хранения: monolith, file-per-entity, directory-per-entity
  - Imports YAML-моделей для композиции/наследования
  - Imports произвольных файлов для генерации (иконки, шаблоны, etc.)
- Принцип «данные отделимы от генерации»: модель не знает что из неё генерируется
- Гибкий метаконфиг:
  - `sources` — определение источников данных (файлы/каталоги)
  - `input` в генераторе — выбор подмножества сущностей/enum'ов/типов
- **Разделение конфигурации**:
  - Application Config — технические настройки (логирование, пути, etc.)
  - Business Config (`.mg.yaml`) — модели, генераторы
- **Нет встроенных генераторов** — все создаются под проект/стек
- **CLI**: гибкий запуск генераторов (-g, список через запятую или повторяющиеся флаги)
- **Архитектура**: ядро + плагины (отдельные пакеты с кодом и шаблонами)
