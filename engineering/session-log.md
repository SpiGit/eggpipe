# Сессия: Разработка Eggpipe

**Даты:**
- 2026-11-03 (первая сессия)
- 2026-11-10 (вторая сессия: архитектура и System Design, нейминг, логирование)
- 2026-11-10 (третья сессия: ревью проектных документов, ТЗ v1.1, ADR-0001)
- 2026-11-11 (четвёртая сессия: ревью v1.1, ТЗ v1.2, System Design v1.2, P0-исправления)
- 2026-11-11 (пятая сессия: harness — repo hygiene и агентские инструкции)
- 2026-11-12 (шестая сессия: TPC-H example, Jinja2-шаблоны и optional helper)
- 2026-11-12 (седьмая сессия: Eggpipe, v2.0, CLI/UX, диагностики, JSON v2)
- 2026-11-13 (восьмая сессия: полное ревью проекта — ТЗ и код, модель Qwen3.8 Max)
- 2026-11-13 (девятая сессия: v2.2, English-only, EG-коды, версия 0.3.0, E9)
- 2026-11-16 (десятая сессия: incremental generation, ADR-0017, ТЗ v2.3, PR-процесс)
- 2026-11-17 (одиннадцатая сессия: per-entity spec, ADR-0018, ТЗ v2.4, PR-процесс)
- 2026-11-18 (двенадцатая сессия: аудит документации, Plugin DX, релиз 0.4.0)
- 2026-11-19 (тринадцатая сессия: политика версий, хвосты 0.4.0, backlog closeout)
- 2026-11-20 (четырнадцатая сессия: план 0.5.0, contract polish, гигиена harness)
- 2026-11-21 (пятнадцатая сессия: watch по ADR-0019, проверка модели, закрытие дня)
- 2026-11-23 (шестнадцатая сессия: публикация ревью, имена сессий, закрытие дня)

**Статус ТЗ:** v2.4 — рабочая версия (замещает v2.3)
**Статус проекта:** beta (0.x); до 1.0 breaking changes возможны (ADR-0014)
**Идентичность:** Eggpipe: package/CLI/config/state; старые имена остаются только в истории и ADR.
**Реализация:** E0–E9 выполнены, релиз `0.4.0` опубликован на PyPI; код и сообщения English-only, EG-коды.
**Code review:** `engineering/reviews/2026-11-13-code-quality-review.md`; skill `clean-code` добавлен; M1/M2/M4/M6/M8 исправлены.
**Patterns review:** `engineering/reviews/2026-11-13-patterns-review.md`; skill `python-patterns` добавлен; P1–P15 применены; continue-аудит: 74 → 39, оставшиеся — guard clauses.
**Project review (2026-11-13):** `engineering/reviews/2026-11-13-project-review.md` — ревью ТЗ и кода (Qwen3.8 Max). Документация: 2 P0 (`GeneratorContext` в примерах README/plugin-guide/ТЗ; skill `plugin-contract` со старым контрактом), 11 P1 (JSON-отчёт `action` vs `status`, `timings`, EG014, дерево модулей, `--plugin`, ТЗ v2.1 и ADR-0011 выпущены), 15 P2. Код: 0 P0, 3 P1 (те же `status`/`timings`; пустой план в `artifact_writer.write()` ломает cleanup), 16 P2; 203 теста passed, ruff/pyrefly чистые. Исправлены P0-1, P0-2, P1-8, P1-10, P1-12, P1-13, K3, K5; ТЗ v2.1 и ADR-0011 выпущены; код P1 исправлен; код P2 K4/K8/K12–K14/K16–K18 исправлен; K10: core → engine устранён; остаётся core.discovery ↔ config.
**Harness:** этапы 0–4 завершены.
**Roadmap:** `engineering/roadmap.md` — направления после 0.4.0 и подготовка к 1.0.
**Ветвление:** trunk-based, без постоянной `develop`; релизы с тегов на `main` (ADR-0015).
**Deprecation:** окно и механизмы предупреждений зафиксированы в ADR-0016.

## Текущее состояние

Документация и код приведены к ТЗ v2.4 (E0–E9). Актуальные решения:

- `ModelDocument` → `SourceModel` → `ModelSlice`; `imports` на уровне документа.
- Per-entity generation реализована: `output_scope`, `Engine.build/generate/check(entities=...)`, CLI `--entity` (ADR-0018).
- `UNSET` vs `default: null`; полная null-матрица.
- `version` формата опционален (latest); смешанные форматы разрешены.
- Model units: `monolith`, `file-per-model`, `directory-per-model`; слои и resources.
- Глобальный manifest `.eggpipe/manifest.json`; lock `.eggpipe/lock`.
- `cleanup: off` по умолчанию; удаляются только неизменённые owned-файлы.
- CLI/JSON v2, `report_version: 2`; exit codes 0/1/2/130.
- Публичный API: `Engine`, `EngineReport`, `Diagnostic`, `ModelSlice`, `FieldDef`,
  `FormatInfo`, `FormatSchema`, `MergePolicy`, `generator`.
- `Field`/`Enum` переименованы в `FieldDef`/`EnumDef`.
- Source code, comments, docstrings, CLI help и diagnostics — English-only (ADR-0012).
- Диагностические коды — `EGxxx`; номера сохранены (ADR-0013).
- `GeneratorRules`/`GeneratorRulesLoader` → `ProjectConfig`/`ProjectConfigLoader`.
- `InputSlice` удалён; используется `InputSelection`; у `CompositionResult` нет `format`/`version`.
- Translation memory: `engineering/i18n/` (ADR-0012).

### v1.4: форматы и model units

- Формат-плагин может расширять формат через одиночное наследование `extends`.
- Версии форматов независимы: `base_versions` задаёт зависимость; `version` опционален (latest).
- `schemas[version]` содержит `layer_entity`/`full_entity`; `layer_entity` — частичная схема, `full_entity` — итоговая.
- Генератор объявляет `input_formats`; совместимость учитывает наследников.
- `@generator` — основной decorator API; классовый `GeneratorPlugin` — advanced.
- В одном запуске допускаются модели разных форматов; несовместимость — EG033.
- Модель = одна сущность; раскладки `monolith`, `file-per-model`, `directory-per-model`.
- `directory-per-model`: явные `model_dirs`/`files`/`resources`, слои форматов, layer merge.
- Ресурсы: top-level `resources` + `models.<dir>.resources`; alias, glob, границы, watch.
- list merge: `fields` — `KEYED`, `types`/`enums` — `APPEND`, неизвестные списки — `ERROR`.
- `Entity.format`/`format_version`/`layer_sources`, `FieldDef.source`,
  `GenerationContext.formats`; `format`/`format_version` удалены.
- `layout` обязателен; legacy discovery удалён.
- manifest v2: глобальный `.eggpipe/manifest.json`, `formats` вместо `format`, v1 не поддерживается.
- `input_formats` обязателен для каждого генератора.
- Новые диагностики: EG027, EG029, EG031–EG038, EG051, EG052, EG301, EG302.
- ADR-0007 — наследование форматов; ADR-0008 — model units и раскладки.

## Реализация v0.1–v0.3

Ядро, composition и delivery:

- `core/model.py` — `FieldDef`, `Entity`, `EnumDef`, `CustomType`, `ModelSlice`, `SourceModel`, `UNSET`.
- `core/document.py` — `ModelDocument`, `ImportSpec`.
- `core/parser.py` — парсер документа, нормализация `version`, формат `entity-model`.
- `core/composition.py` — imports/extends, merge по ADR-0001, project-root, циклы и глубина.
- `core/discovery.py` — файлы и каталоги sources, EG023/EG024.
- `core/provenance.py` — git-дата/хеш источника.
- `watch/watcher.py` — debounce-watch с lazy-import watchdog.
- `core/validator.py` — семантические проверки EG000–EG030 (реализованная часть).
- `core/slicing.py` — `InputSelection` и замыкание среза по enums/types.
- `core/naming.py` — `NamingStyle`, `transform`.
- `interfaces/formats.py`, `engine/format_registry.py` — `FormatPlugin`, `EntityModelFormat`, реестр.
- `interfaces/generator.py` — `GeneratorPlugin`, `GeneratorInput`, `GenerationResult`, `Artifact`.
- `config/app_config.py`, `config/project_config.py` — `AppConfig`, `.eggpipe.yaml`, loader.
- `engine/artifact_writer.py` — пути, ownership, manifest, atomic write, lock, plan/check, cleanup.
- `engine/engine.py`, `engine/report.py`, `engine/plugin_loader.py` — `Engine`, отчёт, entry points.
- `cli/main.py` — `eggpipe generate/init/clean`, `config`, `model`, `gen`, `format`.
- `examples/reference-generator` — reference-плагин; `tests/golden` — golden-тест.
- `examples/tpc-h` + `examples/tpc-h-generator` — TPC-H DDL/Pydantic на одном `model/`,
  split-вариант; Jinja2-шаблоны через optional helper.
- `templating.py` — optional Jinja2 helper (`jinja_environment`, `render_template`) для плагинов.
- `utils/yaml.py` — `ruamel.yaml`, YAML 1.2, duplicate keys → EG000.
- `docs/user/reference/diagnostics.md` — каталог кодов.

`imports` и `extends` поддерживаются с v0.2; композиция идёт по ADR-0001.

Writer/manifest/lock, `Engine`, CLI, reference-плагин и golden-тест реализованы.
Composition v0.2: imports/extends, discovery, `sources[].input`, EG014 и cleanup работают.
v0.3: format-плагины, watch, JSON-отчёт, provenance и `--plugin` реализованы.

## Документы проекта

| Документ | Путь | Статус |
|----------|------|--------|
| ТЗ v2.4 | `engineering/requirements/v2.4.md` | Актуальная рабочая версия |
| ТЗ v2.3 | `engineering/requirements/v2.3.md` | Замещена (история) |
| ТЗ v2.2 | `engineering/requirements/v2.2.md` | Замещена (история) |
| ТЗ v2.1 | `engineering/requirements/v2.1.md` | Замещена (история) |
| ТЗ v1.4 | `engineering/requirements/v1.4.md` | Замещена (история) |
| ТЗ v1.3 | `engineering/requirements/v1.3.md` | Замещена (история) |
| ТЗ v1.2 | `engineering/requirements/v1.2.md` | Замещена (история) |
| ТЗ v1.1 | `engineering/requirements/v1.1.md` | Замещена (история) |
| ТЗ v1.0 | `engineering/requirements/v1.0.md` | Замещена (история) |
| System Design | `engineering/system-design/index.md` | Обновлён до v2.4 |
| ADR-0001 | `engineering/adr/0001-composition-merge-semantics.md` | Принято (уточнено под v1.2) |
| ADR-0002 | `engineering/adr/0002-type-checker-pyrefly.md` | Принято (Pyrefly вместо mypy) |
| ADR-0003 | `engineering/adr/0003-null-semantics.md` | Принято (UNSET/null/default) |
| ADR-0004 | `engineering/adr/0004-ownership-manifest-cleanup.md` | Принято (уточнено ADR-0009) |
| ADR-0005 | `engineering/adr/0005-library-api.md` | Принято (границы library API) |
| ADR-0006 | `engineering/adr/0006-format-extension.md` | Принято (уточнено ADR-0007/0008) |
| ADR-0007 | `engineering/adr/0007-format-inheritance.md` | Принято (наследование форматов) |
| ADR-0008 | `engineering/adr/0008-model-units-and-source-layouts.md` | Принято (model units, раскладки) |
| ADR-0009 | `engineering/adr/0009-global-manifest-ownership.md` | Принято (глобальный manifest) |
| ADR-0010 | `engineering/adr/0010-decorator-generator-api.md` | Принято (decorator API) |
| ADR-0011 | `engineering/adr/0011-public-api-v2-identity.md` | Принято (публичный API v2.1 и идентичность) |
| ADR-0012 | `engineering/adr/0012-english-only-source.md` | Принято (English-only) |
| ADR-0013 | `engineering/adr/0013-diagnostic-code-namespace.md` | Принято (EG-коды) |
| ADR-0014 | `engineering/adr/0014-beta-status-and-compatibility.md` | Принято (beta и совместимость) |
| ADR-0015 | `engineering/adr/0015-branching-and-release-policy.md` | Принято (ветвление и релизы) |
| ADR-0016 | `engineering/adr/0016-deprecation-policy.md` | Принято (deprecation) |
| ADR-0017 | `engineering/adr/0017-incremental-generation.md` | Принято (incremental) |
| ADR-0018 | `engineering/adr/0018-per-entity-generation.md` | Принято (per-entity) |
| Ревью | `engineering/reviews/2026-11-10-project-review.md` | P0 внесены в v1.2; P1/P2 — backlog |

## Harness

| Этап | Статус | Содержимое |
|------|--------|------------|
| 0. Repo hygiene | Готово | `.gitattributes`, `.editorconfig`, `.gitignore` |
| 1. Agent harness | Готово | `AGENTS.md`, `opencode.json`, `.opencode/` |
| 2. Docs/delivery harness | Готово | `tools/check_docs.py`, `.github/workflows/docs.yml` |
| 3. Test harness | Готово | `pyproject.toml`, `uv.lock`, pytest, ruff, Pyrefly, coverage, `.github/workflows/ci.yml` |
| 4. Full delivery | Готово | MIT License, CONTRIBUTING, CHANGELOG, `tools/check_wheel.py`, `.github/workflows/release.yml` |

Агентский harness:

- `AGENTS.md` — короткие правила, карта документов, версионирование, Definition of Done.
- `opencode.json` — `instructions` и запрет правок исторических версий ТЗ.
- `/spec-check` — read-only проверка согласованности (через `spec-reviewer`).
- `/spec-release` — выпуск новой версии ТЗ и синхронизация документов.
- `/adr-new` — создание нового ADR.
- Skills: `spec-consistency`, `plugin-contract`.
- Subagent `spec-reviewer` — read-only ревьюер документации.
- `tools/check_docs.py` — stdlib-чекер документации; CI — `.github/workflows/docs.yml`.
- `pyproject.toml` — пакет, dev-зависимости и конфигурация ruff/Pyrefly/pytest/coverage.
- Dev/CI — `uv` + `uv.lock`; pip остаётся для установки пакета пользователями.
- Тестовый CI — `.github/workflows/ci.yml` (Linux/macOS/Windows × Python 3.11–3.15).
- Delivery: `LICENSE` (MIT), `CONTRIBUTING.md`, `CHANGELOG.md`, `tools/check_wheel.py`.
- Release — `.github/workflows/release.yml` по тегу `v*`: проверки, сборка, smoke-install, GitHub Release.

## Файлы проекта

```
.
├── .editorconfig
├── .gitattributes
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── docs.yml
│       └── release.yml
├── .gitignore
├── .opencode/
│   ├── agents/
│   │   └── spec-reviewer.md
│   ├── commands/
│   │   ├── adr-new.md
│   │   ├── spec-check.md
│   │   └── spec-release.md
│   └── skills/
│       ├── clean-code/
│       │   └── SKILL.md
│       ├── plugin-contract/
│       │   └── SKILL.md
│       └── spec-consistency/
│           └── SKILL.md
├── .session-context.md     # Этот файл
├── AGENTS.md               # Инструкции для агентов
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                 # MIT
├── opencode.json           # Конфигурация OpenCode V2
├── mkdocs.yml             # Docs-site
├── pyproject.toml          # Пакет и конфигурация инструментов
├── pyrightconfig.json      # basedpyright/Pyright
├── uv.lock                 # Зафиксированные dev-зависимости
├── README.md               # Обновлён по v2.4
├── src/
│   └── eggpipe/
│       ├── __init__.py     # Публичный API
│       ├── py.typed
│       ├── cli/
│       │   └── main.py
│       ├── config/
│       │   ├── app_config.py
│       │   └── project_config.py
│       ├── core/
│       │   ├── composition.py
│       │   ├── discovery.py
│       │   ├── paths.py
│       │   ├── document.py
│       │   ├── layers.py
│       │   ├── model.py
│       │   ├── naming.py
│       │   ├── parser.py
│       │   ├── provenance.py
│       │   ├── slicing.py
│       │   └── validator.py
│       ├── engine/
│       │   ├── artifact_writer.py
│       │   ├── engine.py
│       │   ├── format_registry.py
│       │   ├── plugin_loader.py
│       │   └── report.py
│       ├── interfaces/
│       │   ├── diagnostics.py
│       │   ├── formats.py
│       │   └── generator.py
│       ├── templating.py   # Optional Jinja2 helper (extra [jinja])
│       ├── utils/
│       │   ├── exceptions.py
│       │   └── yaml.py
│       ├── watch/
│       │   └── watcher.py
│       └── version.py
├── tests/
│   ├── test_artifact_writer.py
│   ├── test_check_docs.py
│   ├── test_check_wheel.py
│   ├── test_cli.py
│   ├── test_composition.py
│   ├── test_config.py
│   ├── test_contract.py
│   ├── test_determinism.py
│   ├── test_engine.py
│   ├── test_engine_composition.py
│   ├── test_formats.py
│   ├── test_model.py
│   ├── test_naming.py
│   ├── test_package.py
│   ├── test_parser.py
│   ├── test_plugin_loader.py
│   ├── test_provenance.py
│   ├── test_slicing.py
│   ├── test_templating.py
│   ├── test_tpch_example.py
│   ├── test_validator.py
│   ├── test_watch.py
│   └── test_watch_integration.py
├── examples/
│   ├── reference-generator/
│   │   ├── pyproject.toml
│   │   └── src/reference_generator/__init__.py
│   ├── tpc-h/
│   │   ├── model/
│   │   ├── expected/
│   │   ├── .eggpipe.yaml
│   │   └── .eggpipe.split.yaml
│   └── tpc-h-generator/
│       ├── pyproject.toml
│       └── src/tpch_generator/
│           ├── templates/
│           ├── ddl.py
│           ├── generator.py
│           ├── metadata.py
│           └── pydantic_models.py
├── tests/golden/
│   ├── fixtures/models/basic.yaml
│   ├── fixtures/expected/basic.json
│   └── test_golden.py
├── tests/property/
│   └── test_properties.py
├── tools/
│   ├── check_docs.py       # Проверка согласованности документации
│   └── check_wheel.py      # Проверка wheel/sdist и smoke-install
├── docs/
│   ├── index.md
│   ├── user/
│   │   ├── index.md
│   │   ├── quickstart.md
│   │   ├── plugins.md
│   │   └── reference/diagnostics.md
│   ├── ai/
│   │   ├── context.md
│   │   ├── tasks.md
│   │   ├── invariants.md
│   │   └── llms.txt
│   └── engineering/
│       ├── index.md
│       ├── requirements/
│       │   ├── index.md
│       │   ├── v1.0.md … v2.3.md   # История
│       │   └── v2.4.md             # Актуальное ТЗ
│       ├── adr/
│       ├── system-design/
│       ├── reviews/
│       ├── decisions/eggpipe.md
│       ├── plan-v2.md
│       └── release.md
```

## Принятые решения (актуальные)

### Модель данных
- Явные этапы: `ModelDocument` (header + imports + model) → `SourceModel` (после композиции) → `ModelSlice` (замкнутый срез для генератора).
- `metadata` доступен у entity/field/enum/type/source; format-плагин складывает свои поля под namespace формата.
- `default`: отсутствие ключа = `UNSET`, `null` — явное значение. `required=false, nullable=false, UNSET` — валидное состояние.
- Null-матрица (ТЗ §3.6): 12 комбинаций; EG010 — только `nullable=false` + `default=null`; EG011 (warning) — `required=true` + `nullable=true`.
- `constraints` — у поля и CustomType; слияние по атрибутам; неприменимые/противоречивые — EG021.
- `CustomType.base` разрешается транзитивно, цикл/глубина > 10 — EG020.
- `updated_at`/`version` — на уровне entity; устаревшая дата — EG014 (warning, opt-in).
- `required_by_default` удалён.

### Форматы
- `format` обязателен; `version` опционален: нет — latest из `supported_versions`.
- Неизвестный формат — EG007, версия — EG008, без «тихого» default.
- В одном запуске допускаются разные форматы; несовместимый генератор — EG033.
- `entity-model` зарезервирован; format-плагин расширяет через `EntityModelFormat`.
- Версии форматов независимы; `base_versions` задаёт зависимость; `schemas` — схемы по версиям.
- `primitive_types` объявляются форматом; расширение не может их сужать.

### Композиция / merge
- ADR-0001: merge только по явным связям (`imports`/`entity.extends`), аддитивный, детерминированный; конфликты имён — EG002.
- Entity extends: короткое имя или `{import, entity}`; цепочки разрешены; цикл/глубина > 10 — EG009; наследуются `description`, `version`, `updated_at`, `metadata`, `fields`.
- Импорты только внутри project root (EG022), кроме `--allow-outside-imports`; циклы/глубина > 10 — EG006.
- Один resolved-путь обрабатывается один раз; дубли в `sources` — EG024 (warning).
- Discovery каталогов: `**/*.yaml|yml`, лексикографический порядок, пропуск `.git/.eggpipe/output_dir/...`; non-model YAML — EG023.
- Layer merge аддитивный; `fields` — `KEYED`, `types`/`enums` — `APPEND`, неизвестные списки — `ERROR`.

### Срезы и конфиг
- `sources[].input` и `generators[].input` — вложенные объекты (`entities/enums/types`), пусто = все.
- Финальный срез = `generators[].input` по union отфильтрованных sources + closure по enums/types; неизвестное имя — EG018.
- Все пути `.eggpipe.yaml` — от каталога конфига; `-o` заменяет корень.
- `variables` → `context.variables`; CLI > config.

### Плагины
- Два типа: `GeneratorPlugin` (entry points `eggpipe.generators`) и `FormatPlugin` (`eggpipe.formats`).
- `input_formats` обязателен; `None` — любой, `set()` — ни один.
- `api_version` — `ClassVar[Literal["1"]]`; несовместимый не ломает запуск, если не выбран; выбранный → exit 2.
- Вход генератора — `ModelSlice` + `GenerationContext` + `GeneratorConfig`; AppConfig не передаётся.
- Выход — `Artifact(path: относительный POSIX, content: str)`; ошибки → артефакты генератора отбрасываются.
- `@generator` — основной decorator API; классовый `GeneratorPlugin` — advanced.
- `Diagnostic` — структурированный (level, code, message, location) вместо строк.
- Локальные плагины — только editable install; `sys.path`/`plugins_dir` не поддерживаются.

### Запись артефактов
- Ownership: только файлы из location глобального manifest можно перезаписывать/удалять; чужие — EG041, перезапись через `--force`.
- Глобальный manifest: `.eggpipe/manifest.json`, locations `(generator, output_dir)`, пишется атомарно после каждого генератора.
- `eggpipe clean` работает только по manifest, без `.eggpipe.yaml` и плагинов; чистит все locations.
- `on_conflict: overwrite (default) | skip | error`; два location на один путь — EG042.
- Валидация путей: относительный POSIX, без `..`, NUL, backslash, reserved names, длин; NFC; symlink за пределы `output_dir` — EG040; case-collision — EG042.
- Atomic write: staging внутри `output_dir` → `os.replace`; глобальный lock `.eggpipe/lock`; manifest обновляется после каждого генератора.
- Cleanup: `off` (default) | `prompt` (только tty) | `enabled`; удаляются только unchanged owned-файлы; изменённый — EG050 (warning).
- `--plan`/`--dry-run` не создают каталоги и не берут write-lock; `--check` не пишет файлы и не обновляет манифест.

### CLI
- Команды: `eggpipe generate`, `watch`, `init`, `clean`; sub-apps `config show|validate|schema`, `model validate|schema`, `gen list|info`, `format list|info`.
- Флаги: `-g`, `-c`, `-o`, `--var`, `--dry-run`, `--plan`, `--check`, `--clean`, `--strict`, `--force`, `--yes`, `--include-disabled`, `--allow-outside-imports`, `--output-format text|json`, `--ignore`, `--show-secrets`.
- `clean`: `--dry-run`, `--yes`, `--root`.
- Exit codes: 0 успех / 1 errors, drift `--check` или strict warnings / 2 config-usage/plugin/format mismatch / 130 Ctrl+C.
- При падении одного генератора остальные продолжаются.

### Прочее
- Единая точка логирования: `config/logging.py`; без `basicConfig(force=True)`; библиотека не настраивает root-logger.
- CLI-вывод (rich) в stdout, логи в stderr/file — JSON-отчёт не ломается.
- `Engine` — библиотечный фасад: `build()` без записи, `generate()` с записью, `check()` без записи; не вызывает `sys.exit`.
- `ruamel.yaml` + YAML 1.2; `py.typed`; Python 3.11+; `watchdog` — optional extra `[watch]`,
  Jinja2 helper — optional extra `[jinja]`.
- Типизация — Pyrefly (`preset = "strict"`), см. ADR-0002; mypy не входит в блокирующий CI.
- Редактор: basedpyright/Pyright читают `pyrightconfig.json` (src-layout, extraPaths, .venv).
- Dev/CI — `uv` (`uv sync --extra dev`, `uv run`); `uv.lock` коммитится; pip — для установки пакета.
- v0.1: `imports`/`extends` реализованы с v0.2; композиция идёт по ADR-0001.
- Golden-file тесты через reference-плагин из `examples/`.

## Открытые вопросы (future)

| Вопрос | Решение |
|--------|---------|
| Инкрементальная генерация | Реализована в v2.3 (ADR-0017) |
| CI/CD machine-readable | `--output-format json`; расширенная схема — v0.3 |
| Кэширование watch | Простой watch, интерфейс `CacheStrategy` заложен |
| Binary-артефакты | Не-цель v1 |
| Patch-семантика | Future; `required+nullable` — EG011 |
| `--plugin` (dev, без установки) | v0.3+ |
| Provenance (git-дата/хеш) | v0.3 |
| Per-entity `generate()` | Реализовано в v2.4 (ADR-0018) |
| Публикация PyPI `eggpipe` / `eggpipe` | Опубликован `0.3.2` |
| Расширение формата | Решено в v2.0: наследование, `input_formats`, слои (ADR-0007/0008) |

## Следующие шаги (2026-11-13)

1. E2 выполнен: core-модели и публичный API (`FormatInfo`, `FormatSchema`, `MergePolicy`, `Entity.format`, `GenerationContext.formats`).
2. E3 выполнен: наследование форматов, версии, `base_versions`, `schemas`, latest-версия.
3. E4 выполнен: model units, слои, раскладки, ресурсы; TPC-H переведён на directory-per-model.
4. E5 выполнен: decorator API, input_formats, EG033/EG301/EG302.
5. E6 выполнен: глобальный manifest, locations, ownership, cleanup, EG051/EG052.
6. E7 выполнен: CLI/UX, diagnostics, JSON v2, strict/ignore, new schemas/info.
7. E9 выполнен: CI, release workflow, версия пакета 0.3.2.
8. PyPI trusted publisher настроен; тег `v0.3.2` опубликован, пакет доступен на PyPI.


---

## 2026-11-16 — incremental generation и PR-процесс

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | Завершить incremental generation: ADR-0017, ТЗ v2.3, fingerprint, CLI, тесты, docs | Выполнено |
| 2 | Провести PR через CI и ревью | Выполнено, 6 итераций |
| 3 | Смержить и очистить ветки | Выполнено |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| Incremental generation | PR #18: `--incremental`, `input_fingerprint`, `FormatPlugin.input_paths`, `fingerprint_ms`, ADR-0017, ТЗ v2.3 |
| Roadmap PostgreSQL transform | PR #17: пример зафиксирован как кандидат в `0.5.0` |
| PR-процесс | PR #19: Definition of Ready, бюджет 500/15, split rule, review freeze, size-warning, PR-шаблон |
| Очистка | `main` на `dd5d2dd`; ветки #18/#19 удалены локально и на remote |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| PR #19 про процесс PR | PR #18 оказался слишком большим | Появился бюджет размера и review freeze |
| 6 итераций ревью | Контракт формата и locations всплыли поздно | Время, но контракт стал корректнее |
| `FormatPlugin.input_paths` | Сторонние форматы читают файлы вне `model.imports` | Закрыта дыра с устаревшими артефактами |
| `--strict` отключает incremental | На cache hit терялись warnings | Поведение `--strict` согласовано |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| Per-entity generate | Не начинали | 2026-11-17, design-first |
| Улучшение watch | Не начинали | После per-entity |
| Reference-плагины | Не начинали | Параллельно |
| Синхронизация session context/log | Отложено | 2026-11-17 |
| Follow-up minor `create_pr.py` | Вынесены | 2026-11-17 |

### 5. План на 2026-11-17

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | Перезапустить `ci` на `dd5d2dd` | macOS 3.11 cancelled | Уверенность в зелёном main | 5 минут |
| 2 | Day-closure и session sync | AGENTS/CONTRIBUTING + session-файлы | Повторяемое закрытие дня | docs |
| 3 | Follow-up `create_pr.py` | renames, `fnmatchcase`, size exception | Надёжный size-check | chore |
| 4 | Per-entity spec/ADR | CLI/API, ownership, incremental | Разблокирует P1 | spec |

Параллельно: PR A (docs) и PR B (chore) в отдельных worktree, файлы не пересекаются.
PR C — после PR A.


---

## 2026-11-17 — per-entity generation и очистка процесса

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | Перезапустить `ci` на `dd5d2dd` | Выполнено |
| 2 | Day-closure и session sync | Выполнено (#20) |
| 3 | Follow-up `create_pr.py` | Выполнено (#21, #23) |
| 4 | Per-entity spec/ADR | Выполнено (#26) |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| Day closure | #20: `day-closure.md`, Backlog candidates, параллельная работа |
| create_pr follow-up | #21, #23: renames, `numstat -z`, size exception, авто-блок размера |
| Git env isolation | #22: preflight/provenance не наследуют `GIT_*` |
| Backlog process | #24, #25, #27: backlog, ID, закрытие, grooming |
| Per-entity spec | #26: ТЗ v2.4, ADR-0018, output_scope, EG303 |
| Process optimization | #28–#30: backlog cleanup, shared-file warning, rebase policy |
| Backlog closeout | #31: Backlog candidates, B-021/B-023 |
| Per-entity engine | #32: entities selection, manifest merge, cleanup off |
| Per-entity CLI/docs | #33: `--entity`, watch rejection, docs, tests |
| Итог | `main` 953e4d5; 295 тестов; coverage 84.60% |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Git hook pollution | `GIT_DIR` из pre-push попал в provenance-тест | Commit/core.bare в repo; исправлено #22 |
| Backlog cleanup | B-001–B-022 накопились за ревью | Все закрыты (B-021 — в #32); открыты B-023 и B-024 |
| Per-entity реализация | Спецификация и engine/CLI сделаны в тот же день | P1 закрыт раньше плана |
| Process optimizations | Долгие rebase и конфликты | shared-file warning, rebase policy, rerere |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| B-023: tests+coverage в PR body | Отложено | 2026-11-18 |
| B-024: тесты merge formats/generated_at | Найдено на ревью #32 | 2026-11-18 |
| Улучшение watch | Не начинали | После релиза 0.4.0 (0.5.0) |
| Reference-плагины, метрики | Не начинали | Reference — 0.4.0; метрики — 0.5.0 |

### 5. План на 2026-11-18

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | B-023: coverage в PR body | `create_pr.py` + `coverage.xml`/`--coverage` | Видимость покрытия | chore, ~100 строк |
| 2 | B-024: merge formats/generated_at tests | per-entity manifest | Закрыть пробел покрытия | test, ~50 строк |
| 3 | Аудит инженерной документации | ТЗ, ADR, System Design, roadmap, session-log | Убрать stale-статусы | docs |
| 4 | 0.4.0 Plugin DX | template, contract-test kit, examples, docs | Закрыть текущий релиз | feat/docs |

---

## 2026-11-18 — релиз 0.4.0 и Plugin DX

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | B-023: coverage в PR body | Выполнено (#38) |
| 2 | B-024: тесты merge `formats`/`generated_at` | Выполнено (#37) |
| 3 | Аудит инженерной документации | Выполнено (#39) |
| 4 | 0.4.0 Plugin DX | Выполнено (#40–#43), релиз (#45) |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| create_pr coverage | #38: `--tests`/`--coverage`, блок «Проверки», warning по shared-файлам |
| Manifest merge tests | #37: тесты merge `formats`/`generated_at` |
| Аудит документации | #39: P0/P1 исправлены, отчёт `reviews/2026-11-18-engineering-audit.md`, P2 → B-025 |
| Copier-шаблон | #40: `examples/plugin-template-copier`, валидаторы, CI рендера |
| Info-команды | #41: `module`/`class`/`api_version`/`base_versions`, did-you-mean, EG-код в warning, «Первый плагин за 10 минут» |
| Reference-примеры | #42: `examples/reference-generators` (SQL, Pydantic, TypeScript, OpenAPI), cookbook, CI job |
| Ошибки контракта | #43: EG301/EG302 с плагином, местом и hint; `PluginIssue.code`; границы кода по ТЗ v2.4 |
| Backlog closeout | #44: B-026–B-033 из ревью, roadmap/session-context синхронизированы |
| Релиз 0.4.0 | #45: версия, CHANGELOG, mike `0.4`, матрица ТЗ; тег `v0.4.0`, PyPI, GitHub Release, SBOM, docs `/0.4/` |
| Пост-релиз | #46: статус «опубликован», ТЗ v2.4, roadmap §1/§4/§8, B-034 |
| Итог | `main` d76ff65; 324 теста; coverage 84.88% |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Параллельные потоки в worktree | Plugin DX состоял из трёх независимых задач | Три PR одновременно; конфликт только в `CHANGELOG.md` |
| #41 закрыт без merge | Ошибка при мерже, обнаружилась по `merged=false` | PR переоткрыт, отребейзен на #43, тест warning выровнен; код контракта снова печатается |
| Backlog вырос до 10 | Minor из ревью #41–#46 | B-026–B-034; лимит достигнут, перед добавлением нужен grooming |
| Удаление старых веток | `origin/feat/plugin-dx-contract` (#43) и локальная `chore/create-pr-followup` (#21) остались | Ветки удалены, остался только `main` |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| B-025: P2 аудита (v2.1 refs, ADR legacy, терминология, docs/ai freshness, format API) | Не начинали | следующий этап, до 0.5.0 |
| 0.5.0: watch, L2/L3, auto-discovery, метрики | Не начинали по правилу «не начинать до релиза 0.4.0» | 0.5.0 |
| Minor из ревью #45/#46 | Лимит backlog 10 | Grooming + B-034 |

### 5. План на следующий день

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | Grooming backlog B-025–B-034 | Лимит 10, есть дубли и разросшиеся записи | Освободить место, сгруппировать долг | docs, ~1 ч |
| 2 | B-034 + кандидаты из #46 | CHANGELOG-дубль, примеры `system-design`, stale-раздел аудита | Документы без stale-ссылок | docs |
| 3 | B-026/B-033: CLI info | `format list` поля, did-you-mean в `cli.md`, тестовые пробелы | Полная картина плагинов | feat/docs, ~150 строк |
| 4 | План 0.5.0 | watch, L2/L3, auto-discovery, метрики | Зафиксировать scope вехи | docs/spec |

---

## 2026-11-19 — политика версий и закрытие хвостов 0.4.0

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | Grooming backlog B-025–B-034 | Выполнено (#48) |
| 2 | B-034 и minor из ревью #46 | Выполнено (#50) |
| 3 | B-026/B-033: CLI info | Выполнено (#49) |
| 4 | План 0.5.0 | Не начато |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| Grooming backlog | #48: слияние B-030/B-032/B-033, перенос B-028 в roadmap 0.6.0, открытых 6 |
| CLI info | #49: `format list` показывает `api_version`/`extends`/`base_versions`, тест наследования, docs |
| Пост-релизные docs | #50: порядок секций CHANGELOG, версии в `system-design`/`session-log` заменены на плейсхолдеры |
| Политика версий | #51: `DOC161` (литерал версии вне allowlist), `tools/bump_version.py`, mike-версия из `pyproject.toml`, чистка живых доков |
| Discovery DX | #52: подсказка `gen list --all`, обязательная группа в `_patch_entry_points` |
| Reference-примеры | #53: пин `>=0.4.0`, pyrightconfig, ссылка в README, cookbook, тесты options/discovery |
| Backlog closeout | #54: закрыты B-026/B-027/B-029/B-034, добавлены B-035–B-042 |
| Итог | `main` c224b90; 349 тестов; coverage 84.94% |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Политика версий | Владелец указал на шум от ручного обновления версий в доках | Один источник версии, CI ловит хардкод (`DOC161`), релиз одной командой |
| B-027/B-029 | Остатки minor из ревью плагинных PR | Закрыты в тот же день; лимит backlog снова 10 |
| `DOC161` поймал cookbook | Проверка сработала на прозе с `0.4.0` | Формулировка переписана без литерала — правило работает на практике |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| План 0.5.0 | День ушёл на политику версий и хвосты 0.4.0 | 2026-11-20 |
| B-025: P2 аудита | Не начинали | до 0.5.0 |
| B-031: contract errors polish | Не начинали | 2026-11-20 |
| Grooming backlog | Открытых 10 (лимит) | перед следующей фичей |

### 5. План на 2026-11-20

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | План 0.5.0 | Приоритеты watch, L2/L3, метрики, бенчмарки | Зафиксировать scope вехи | docs/spec |
| 2 | B-031: contract errors | Код декорирования, общий модуль location, hint-константы | Последовательный вывод ошибок | feat, ~200 строк |
| 3 | B-035: тесты `bump_version.py` | `main()`/`--dry-run`, `REQUIRED_FILES` | Защита релизного скрипта | test/chore |
| 4 | B-039: docs-единообразие | `release.md` пути/пример, термин «проверка» | Меньше расхождений в docs | docs |

---

## 2026-11-20 — план 0.5.0 и гигиена harness

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | План 0.5.0: scope и порядок | Выполнено (#59) |
| 2 | B-031: contract errors polish | Выполнено (#56) |
| 3 | B-035: тесты `bump_version.py` | Выполнено (#57) |
| 4 | B-039: docs-единообразие | Выполнено (#58) |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| План 0.5.0 | #59: порядок watch → L2/L3 → метрики (ТЗ v2.5) → бенчмарки, non-goals и критерии |
| Contract errors | #56: `core/plugin_contract.py`, EG301 для аргументов `@generator(...)`, единые hint-константы |
| Релизный скрипт | #57: тесты `main()`/`--dry-run`/ошибок, `REQUIRED_FILES` |
| Release guide | #58: примеры путей и терминология `DOC161` |
| Гигиена сессий | #60: правило «сессия — задача/день», «Критерии приёмки», пакет ревью |
| preflight stamp | #61: пропуск тяжёлых проверок при неизменном дереве, безопасный набор хешей |
| Итог | `main` 6828700; 365 тестов; coverage 85.01% |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Анализ расхода контекста | Вопрос владельца про токены | Найдено: ~400k промпта на шаг из-за длинной сессии; приняты #60/#61 |
| Merge day closure 19-го | #55 был готов, но не смержен | Состояние зафиксировано |
| Backlog 10 → 8 | Закрыты B-031/B-035/B-039, добавлен B-043 | Лимит разгружен |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| Watch (0.5.0) | День ушёл на harness и хвосты | 2026-11-21, новой сессией |
| B-025: P2 аудита | Не начинали | до 0.5.0 |
| L2/L3 | Не начинали | 2026-11-21 (spike) |

### 5. План на 2026-11-21

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | ADR-0019 + design note watch | сериализация, `max_delay`, границы отмены | Зафиксировать контракт до кода | spec/docs, ~1 с. |
| 2 | Watch: `max_delay` и один прогон | тесты серии событий во время прогона | Нет отложенных сборок | feat, ~200 строк |
| 3 | L2/L3 spike | гранулярность кэша, сценарий «изменён один из N» | Понять выигрыш до реализации | docs/spike |
| 4 | Grooming backlog | 8 открытых, B-043 | Свободное место | docs |

---

## 2026-11-21 — watch по ADR-0019, проверка модели и закрытие дня

### 1. План на день

| # | Задача | Статус |
|---|--------|--------|
| 1 | ADR-0019 + design note watch | Выполнено 2026-11-20 (#63) |
| 2 | Watch: `max_delay`, ожидание прогона, wiring `--debounce-ms` | Выполнено (#65) |
| 3 | L2/L3 spike | Не начато |
| 4 | Grooming backlog | Частично: открытых 10, добавлены B-045/B-046 |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| Watch по ADR-0019 | #65: `max_delay = 10 × debounce_ms`, сериализация G1–G4, ровно один follow-up; первый Ctrl+C отменяет запланированное и ждёт текущий прогон (exit 0), повторный — exit 130; `--debounce-ms` из `AppConfig` (`EGGPIPE_WATCH_DEBOUNCE_MS`); +11 тестов |
| B-044 | Закрыт в #65: уточнения ADR-0019 §3.1–3.2/§4/§6, ссылка в README, титул в `adr/index.md` |
| Синхронизация docs | System Design §9, `docs/user/cli.md`, CHANGELOG, пересборка `docs/ai/llms-full.txt` |
| Проверка модели в harness | #66: первая проверка AGENTS.md — сессия только на Flash-модели, иначе остановка и явное подтверждение |
| Итог | `main` b1c0d14 (#65, #66); 376 тестов; coverage 85.54% |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Проверка модели сессии | Запрос владельца | Защита от запуска сессии на не-Flash модели |
| Backlog closeout #65 | Пять minor ревью | B-045 |
| Backlog closeout #66 | Две minor ревью; ревью #66 вернулось после merge #67 | B-046 |
| Post-merge cleanup #65 | Процесс | Ветка удалена, `main` подтянут |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| L2/L3 spike | Время ушло на реализацию watch и harness | 2026-11-22 |
| Grooming backlog | Частично: лимит 10 не превышен, открытых 10 | 2026-11-22 |

### 5. План на 2026-11-22

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | L2/L3 spike | гранулярность кэша, сценарий «изменён один из N файлов» | Понять выигрыш до реализации | docs/spike |
| 2 | B-036: `troubleshooting.md` | подсказка `gen list --all`, формулировка CHANGELOG | DX при сломанных плагинах | docs |
| 3 | B-037: общий хелпер entry points | инлайновые `fake_entry_points` в `test_cli.py`/`test_plugin_loader.py` | Изоляция групп плагинов в тестах | test/chore |
| 4 | Grooming backlog | открытых 10 | Место под 0.5.0 | docs |

---

## 2026-11-23 — публикация ревью ревьюером, имена сессий и закрытие дня

### 1. План на день

План перенесён с 2026-11-22 (рабочего дня не было).

| # | Задача | Статус |
|---|--------|--------|
| 1 | L2/L3 spike | Не начато |
| 2 | B-036: `troubleshooting.md` | Не начато |
| 3 | B-037: общий хелпер `entry_points` | Не начато |
| 4 | Grooming backlog | Не начато |

### 2. Выполнено

| Задача | Результат |
|--------|-----------|
| Закрытие #68 | APPROVE итерации 2, merge, post-merge cleanup; фиксы ревью #67 (B-046, формат B-045, stale-счётчики roadmap/session-log) в `main` |
| Harness #69 | `pr-reviewer` публикует вердикт сам: точечный `allow` для `tools/review_pr.py`, раздел «Публикация» (heredoc с quoted-разделителем, `event=COMMENT`, fallback); каждая итерация остаётся в истории PR |
| Имена сессий | Правило в `AGENTS.md`/`CONTRIBUTING.md`: `session_rename` — задача → `#<PR> <задача>` → `[closed]`; применено к текущей сессии |
| История ревью | Ретроспективно опубликованы итерации 1 для #66 и #68 (COMMENT), чтобы промежуточные вердикты не терялись |
| B-046 | Закрыт в #69: CHANGELOG о harness-изменениях (Flash-проверка, публикация ревью, имена сессий); уточнено поведение subagent'а с собственной не-Flash моделью |
| Итог | `main` e1e0885 (#67–#69); 376 тестов; coverage 85.54%; backlog 9 |

### 3. Вне плана

| Что | Причина | Импакт |
|-----|---------|--------|
| Публикация ревью ревьюером | Запрос владельца: комментарии не должны теряться | Каждая итерация видна в PR |
| Имена сессий | Запрос владельца: навигация по сессиям | `#<PR>` и `[closed]` в имени |
| Ретроспектива ревью | Найдено при разборе «почему не видно итерацию 1» | Восстановлена история #66/#68 |

### 4. Не выполнено

| Задача | Причина | Перенос |
|--------|---------|---------|
| L2/L3 spike | День ушёл на процесс ревью и закрытие хвостов | следующий рабочий день |
| B-036, B-037 | Приоритет у процесса ревью | следующий рабочий день |
| Grooming backlog | Не начинался | следующий рабочий день |

### 5. План на 2026-11-24

| # | Задача | Контекст | Импакт | Формат / оценка |
|---|--------|----------|--------|-----------------|
| 1 | L2/L3 spike | гранулярность кэша, сценарий «изменён один из N файлов» | Понять выигрыш до реализации | docs/spike |
| 2 | B-036: `troubleshooting.md` | подсказка `gen list --all`, формулировка CHANGELOG | DX при сломанных плагинах | docs |
| 3 | B-037: общий хелпер entry points | инлайновые `fake_entry_points` в `test_cli.py`/`test_plugin_loader.py` | Изоляция групп плагинов в тестах | test/chore |
| 4 | Grooming backlog | открытых 9 | Место под 0.5.0 | docs |
