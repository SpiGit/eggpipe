# Changelog

Все заметные изменения проекта. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- JSON-отчёт `report_version: 3`: блок `cache` с метриками L2 (`hits`, `misses`,
  `miss_reasons`, `entries`, `bytes`); ADR-0021.
- Структурированные логи: `EGGPIPE_LOG_MODE=json` — JSON Lines в stderr
  (`ts`, `level`, `logger`, `message`; опционально `run_id`, `event`, `duration_ms`,
  `exception`, `extra`).

### Changed

- `tools/benchmark.py` измеряет регрессионные сценарии TPC-H (полный `generate`,
  incremental no-op и «изменён 1 из 8») на временной копии примера; baseline предыдущего
  релиза и пороги — `engineering/benchmarks.md`.
- Процесс: сессии и backlog описаны в `engineering/process/sessions.md`, ритуалы — команды
  `/session-start` и `/session-close`; backlog закрывается в `engineering/backlog-archive.md`
  с лимитом 10 `open`.
- `tools/preflight.py --stamp` пропускает тяжёлые проверки при неизменном дереве
  (хеш по `src`, `tests`, `tools`, `examples`, `docs`, `engineering`, `.github`, `.opencode`,
  конфигам и корневым документам).
- Harness: короткие сессии и передача состояния через `.session-context.md`;
  «Критерии приёмки» в PR-шаблоне; ревьюер работает по пакету «diff + файлы + критерии».
- Harness: первая проверка сессии — только Flash-модель, иначе остановка и явное
  подтверждение пользователя.
- Harness: `pr-reviewer` сам публикует вердикт в PR через `tools/review_pr.py`;
  каждая итерация ревью видна в истории. Имя сессии — готовая строка для копирования в
  первом ответе, `#<PR>` после создания PR, `(closed)` при закрытии.
- Harness: `pr-reviewer` публикует вердикт через `--body-file` (heredoc не нужен);
  запись разрешена только в `/tmp/opencode/**`. Лимит — 40 шагов; вердикт обязан
  соответствовать находкам: Critical/Major ⇒ `CHANGES REQUESTED`.
- Ошибки аргументов `@generator(...)` приходят из загрузчика с кодом `EG301` и подсказкой;
  общие hint-константы и формат локации вынесены в `core/plugin_contract.py`.
- Релизная подготовка автоматизирована: `tools/bump_version.py` обновляет версию,
  `uv.lock`, CHANGELOG и `docs/ai`; `pages` вычисляет версию docs из `pyproject.toml`.
- `check_docs.py` отклоняет литерал текущей версии в живых документах (DOC161).
- `eggpipe gen list` подсказывает `gen list --all`, если ни один генератор не загрузился;
  общий тестовый хелпер `patch_entry_points` фильтрует плагины по группе.
- `eggpipe format list` показывает `api_version`, `extends` и `base_versions`, как `format info`.
- `eggpipe watch` — планирование прогонов по ADR-0019: серия правок даёт один прогон
  с потолком `max_delay = 10 × debounce_ms`, параллельные прогоны исключены, первый Ctrl+C
  дожидается завершения текущего прогона (exit 0), повторный — немедленный exit 130;
  default `--debounce-ms` берётся из `EGGPIPE_WATCH_DEBOUNCE_MS`/`.env`.

### Fixed

- Кэш разбора документов (`--incremental`) устойчив к повреждённому payload: битый тег
  скаляра, неизвестный тип, невалидный `date`/`decimal` и глубокая вложенность дают промах
  и полный разбор вместо падения прогона. Пользовательские словари с ключом
  `__eggpipe_type__` больше не интерпретируются как теги: кодировка payload сменилась,
  поэтому прежний кэш один раз промахивается (`cache_version` 2).

## [0.4.0] - 2026-11-18

### Added

- `engineering/backlog.md` — единое место для отложенных minor и техдолга.
- `examples/plugin-template-copier` — one-command шаблон плагина через copier и CI-проверка рендера.
- Раздел «Первый плагин за 10 минут» в `docs/user/plugin-template.md`.
- `examples/reference-generators` — reference-примеры генераторов SQL, Pydantic, TypeScript
  и OpenAPI вне TPC-H, с contract-тестами и cookbook-страницей.
- `--incremental` / `EGGPIPE_INCREMENTAL=true` — opt-in кэш на уровне location:
  пропуск parse/validate/generate при совпадении fingerprint входа и хэшей артефактов;
  отключается при `--check`, `--force`, `--clean`, `--strict`, `diagnostics.stale_dates`,
  `--entity` и внешних импортах.
- `engineering/day-closure.md` — шаблон закрытия дня; разделы «Параллельная работа» и
  «Закрытие дня» в `AGENTS.md`/`CONTRIBUTING.md`.
- `FormatPlugin.input_paths` — декларация файлов, влияющих на парсинг формата;
  `None` отключает incremental.
- `timings.fingerprint_ms` — время сбора входного fingerprint.
- ТЗ v2.3: контракт инкрементальной генерации и отчёт cache hit.
- ТЗ v2.4: контракт per-entity генерации, `output_scope`, `--entity` и EG303.
- Per-entity generation: `output_scope`, `Engine.build/generate/check(entities=...)`,
  CLI `--entity`, manifest merge, cleanup off, EG303.
- `examples/plugin-template` — шаблон генератора и формата с contract-тестами.
- Страница `docs/user/plugin-template.md` и CI-проверка шаблона.
- `tools/create_pr.py` — создание PR с заполнением «Что изменено» из коммитов,
  предупреждение о превышении бюджета и `--allow-large "reason"`.
- AGENTS/CONTRIBUTING/PR-шаблон: Definition of Ready, бюджет PR, split rule и review freeze.
- ADR-0016: политика deprecation для публичного API, CLI, конфига и плагинов.
- `tools/benchmark.py` и `engineering/benchmarks.md` — базовые замеры TPC-H.
- Release workflow генерирует CycloneDX SBOM и прикладывает его к GitHub Release.
- Версионированная документация: `mike`, версии `major.minor` и alias `latest`.
- PR-ревью через subagent `pr-reviewer` (Qwen3.8 Flash) и `tools/review_pr.py`.

### Changed

- `eggpipe gen info` и `eggpipe format info` показывают `module`, `class`, `api_version`,
  `base_versions`, а при неизвестном id подсказывают ближайшие имена и доступные плагины.
- Сообщения `EG301`/`EG302` называют плагин и место ошибки и подсказывают, что исправить;
  `PluginIssue` заполняет код диагностики для contract-ошибок.
- `engineering/requirements/index.md` разделён на реестр версий и `changelog.md`.
- `.session-context.md` сокращён до текущего состояния; история вынесена в
  `engineering/session-log.md`.
- Manifest state: `ManifestLocation.input_fingerprint` — необязательный hex SHA-256 входа
  (ADR-0017). Старые manifest v2 читаются; более старая Eggpipe новый manifest не прочитает.
- `--verbose` включает DEBUG-логи, в том числе причину отключения incremental-кэша.
- `tools/create_pr.py` обновляет блок размера в PR body по маркерам и сохраняет
  ручную карту ревью при повторном запуске; предупреждает об изменении shared-файлов.
- Backlog ведётся одной таблицей со статусом, без переноса строк между секциями.
- Backlog closeout: отложенные minor копятся в `Backlog candidates` PR body и переносятся
  в backlog одним PR в конце дня.
- PR-процесс: rebase только при `behind`/`dirty`, squash WIP перед rebase, `rerere`/`zdiff3`.
- PR-шаблон и процесс ревью требуют фиксировать отложенные minor в `Backlog candidates`.
- `tools/create_pr.py`: сохраняет `## Size exception` при обновлении PR и отклоняет
  пустой `--allow-large`.
- `tools/create_pr.py`: `--tests` и `--coverage` добавляют в PR body блок «Проверки»
  по маркерам и сохраняют остальные секции при обновлении.

### Fixed

- `tools/create_pr.py`: size-check разбирает `git diff --numstat -z`; при повреждённом
  `pr-size:start` не теряет ручные секции body.
- `tools/preflight.py` и provenance-тесты не наследуют `GIT_*` из pre-push hook;
  временный git-репозиторий больше не может изменить основной репозиторий.

## [0.3.2] - 2026-11-14

### Changed

- Project URL `Documentation` на PyPI указывает на опубликованный сайт
  https://spigit.github.io/eggpipe/.

## [0.3.1] - 2026-11-13

### Changed

- PyPI-страница использует отдельный пользовательский `README-pypi.md` без инженерной
  документации и команд разработки.
- Основной `README.md` остаётся полным описанием для GitHub.

## [0.3.0] - 2026-11-13

### Changed

- ТЗ v2.2: English-only source code, comments, docstrings, CLI help и diagnostics.
- Диагностические коды `MGxxx` → `EGxxx`; номера сохранены (ADR-0013).
- `GeneratorRules`/`GeneratorRulesLoader` → `ProjectConfig`/`ProjectConfigLoader`;
  `config/generator_rules.py` → `config/project_config.py`.
- Удалён `InputSlice`; публичный тип выбора входа — `InputSelection`.
- Удалены legacy-поля `CompositionResult.format`/`version`.
- Унифицированы ignore-константы; `WIN_RESERVED` → `WINDOWS_RESERVED_NAMES`.
- Translation memory русских сообщений и docstrings: `engineering/i18n/`.
- ADR-0012 (English-only) и ADR-0013 (EG-коды).
- Проект объявлен beta (0.x): до 1.0 breaking changes возможны (ADR-0014).
- CI-матрица расширена до Python 3.11–3.15.
- Проект переименован в **Eggpipe**: CLI `eggpipe`, конфиг `.eggpipe.yaml`, state `.eggpipe/`,
  package/import `eggpipe`.
- ТЗ v2.0: breaking changes, решения v1.4 вошли без изменения смысла.
- CLI/UX, diagnostics и JSON-отчёт v2 зафиксированы.
- Переименование кода/пакета выполнено: `eggpipe`, `eggpipe.*`, `.eggpipe*`.
- Реализованы форматы/наследование, model units и слои, resources, decorator API,
  `input_formats`/EG033, глобальный manifest/ownership/cleanup, CLI и JSON v2.
- TPC-H example переведён на `directory-per-model` и decorator API.

## [0.1.0] - 2026-11-11

### Added

- Ядро v0.1, первый слой: `ModelDocument`/`SourceModel`/`ModelSlice`, `FieldDef`, `EnumDef`,
  `CustomType`, `UNSET`, YAML-парсер на `ruamel.yaml`, формат `entity-model`, семантический
  валидатор, срезы с замыканием по enums/types и naming-утилиты.
- Writer: ownership, per-generator manifest, atomic write, lock, `--plan`/`--check`.
- `Engine` (`build()`/`generate()`/`check()`), `GeneratorPlugin` и контракты генераторов.
- CLI `mg`: `generate`, `init`, `config show/validate`, `model validate`, `gen list/info`,
  `format list`, `clean`.
- Reference-плагин `examples/reference-generator` и golden-тест.
- v0.2: composition — `imports`, `entity.extends`, discovery каталогов, merge по ADR-0001,
  project-root boundary и `--allow-outside-imports`.
- Cleanup owned-артефактов (`off|prompt|enabled`), `--clean`, MG050.
- `sources[].input` и MG014 (`updated_at`).
- v0.3: format-плагины из entry points, `mg watch`, JSON-отчёт, provenance-утилита,
  `--plugin` для локальной разработки.
- Стабилизация: integration-тест watch, contract-тесты плагинов, security-тест symlink,
  руководство `docs/plugin-guide.md`.
- ADR-0003 (null-семантика/UNSET), ADR-0004 (ownership/cleanup), ADR-0005 (library API),
  ADR-0006 (format extension) и индекс ADR.
- `UNSET` больше не сериализуется как `default: null` — ключ опускается.
- `on_conflict: error` теперь даёт MG041 для любого существующего файла; `mg clean` берёт lock.
- Provenance на уровне entity: `Entity.source` заполняется парсером, исключён из сериализации;
  `git_provenance()` доступен плагинам.
- Docs-site: `mkdocs.yml`, `docs/index.md`, сборка `mkdocs build --strict` в CI.
- Property-based тесты (Hypothesis) для парсера и round-trip; determinism-тест повторной генерации.
- Backlog P1/P2: `mg model schema`, `mg config schema`, единая точка logging,
  интерактивный `mg clean --yes`, устойчивый plugin loader с issues, флаги watch.
- ТЗ v1.3: зарегистрированы MG030/MG300, диапазоны кодов и публичный API синхронизированы
  с реализацией; `Entity.source` и fallback `cleanup: prompt`.
- TPC-H example: 8 таблиц, PostgreSQL DDL и Pydantic-модели; варианты одного/split генератора
  на одном наборе `model/`; Jinja2-шаблоны с `options.templates_dir`.
- Опциональный `metadata_generator.templating` (extra `[jinja]`): загрузка Jinja2-окружения
  и `render_template`, ядро не импортирует Jinja2 при старте.
- Каталог диагностик `docs/reference/diagnostics.md`.
- ТЗ v1.2: модель `ModelDocument` → `SourceModel` → `ModelSlice`, контракты плагинов,
  ownership/manifest, CLI и диагностики.
- System Design v1.2 и ADR-0001 (семантика композиции).
- Agent harness: `AGENTS.md`, `opencode.json`, команды, skills и read-only `spec-reviewer`.
- Python-чекер документации `tools/check_docs.py` и docs-CI.
- Test harness: `pyproject.toml`, `uv.lock`, ruff, Pyrefly (strict), pytest, coverage.
- ADR-0002: Pyrefly вместо mypy.
- Delivery harness: сборка wheel/sdist, проверка артефактов и release-workflow.
- MIT License.

### Fixed

- `Entity.updated_at` сохраняет `datetime` при JSON round-trip, включая значения на полночь.
