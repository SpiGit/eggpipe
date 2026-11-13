# Code Quality Review — 2026-11-13

**Область:** `src/eggpipe`, `examples/*/src`, тесты — read-only ревью.
**Основание:** skill `clean-code`, ТЗ v2.0, System Design, ADR-0001.
**Статус:** отчёт; код не изменялся.

## Резюме

Архитектурные границы в целом соблюдены: `core` не зависит от CLI/engine, доменные модели
immutable, диагностики структурированы, публичный API типизирован. Основной долг — не в
отдельных «плохих строках», а в концентрации логики:

- оркестрация в `Engine.build` и `Engine._run_generator`;
- CLI с 19 параметрами и duplicated policy;
- branch-heavy `ArtifactWriter.plan`/`write`;
- повторяющиеся проверки формата/версии в `Composition`;
- 96 строковых литералов диагностик и несколько наборов дублирующихся констант.

Метрики по `src/eggpipe`:

| Метрика | Значение |
|---------|----------|
| Строк кода | 4064 |
| Функций длиннее 40 строк | 16 |
| Максимальная вложенность | 4 (`Composition.resolve`, `ArtifactWriter.write`, `select_slice`) |
| Строк с `if` | около 240 |
| Литералов `MGxxx` | 96 вхождений, 34 уникальных кода |
| Самые длинные функции | `ArtifactWriter.plan` (120), `Composition.resolve` (90), `Validator._validate_entity` (89), `Engine.build` (84), `ArtifactWriter.write` (82) |

## Follow-up

После ревью исправлены быстрые дефекты:

- **M4** — мёртвая ветка `on_conflict == "error"` удалена, `PlannedArtifact` собирается через
  `_planned()`; поведение покрыто существующими тестами.
- **M6** — `load_formats_with_issues`, `build_format_registry_with_issues` и
  `load_local_generators_with_issues` возвращают `PluginIssue`; CLI печатает warnings.
- **M8** — пустой `primitive_types` больше не подменяется встроенными примитивами.

Остальные пункты остаются в плане по приоритетам.

## Major

### M1. `Engine._run_generator` зависит от скрытого `self._composition`

**Где:** `src/eggpipe/engine/engine.py:252-285`.

Метод принимает `model`, но `imports` и `documents` берёт из `self._composition`, который
выставляется в `build()` (строка 97). Это временная связь: метод нельзя вызвать отдельно,
он может увидеть `composition` от предыдущего запуска, а проверка `self._composition is None`
стоит уже после `select_slice`.

**Предложение:** передавать `CompositionResult` явно:

```python
def _run_generator(
    self,
    composition: CompositionResult,
    generator_config: GeneratorConfig,
    plugin: GeneratorPlugin,
) -> tuple[GenerationResult, ExecutionPlan]:
```

`GenerationContext` собирать из `composition` и среза, а `self._composition` оставить только
для `generate()`/`check()` либо убрать полностью.

### M2. `Engine.build` смешивает пять фаз

**Где:** `src/eggpipe/engine/engine.py:80-163`.

В одной функции: discovery, composition, валидация модели, запуск генераторов, сборка
отчёта и накопление `_pending`. Отсюда ранние возвраты с разными аргументами `_report`
и двойная фильтрация ignored-диагностик.

**Предложение:** разбить на фазы с явным результатом:

- `_load_composition() -> CompositionResult | None`;
- `_validate_model(composition) -> list[Diagnostic]`;
- `_run_generators(model) -> GeneratorRunResult`;
- `_finish(...)`.

`_pending` заменить на локальный список, возвращаемый из `_run_generators`.

### M3. CLI дублирует параметры и политику exit code

**Где:** `src/eggpipe/cli/main.py:158-215`, `219-269`, `289-370`, `105-148`.

`_run_engine` принимает 19 параметров; `generate` и `watch` почти полностью повторяют
декларации опций. `_print_report` заново вычисляет `success` и `exit_code` по диагностикам,
игнорируя `EngineReport.success`/`exit_code`, хотя Engine уже применил свою политику.

**Предложение:**

- `@dataclass(frozen=True) class RunOptions` для общих флагов; Typer-команды собирают его.
- Одна функция `resolve_exit_code(report, *, strict)` в `engine/report.py`; CLI только
  печатает и возвращает код.
- Один декоратор/хелпер для преобразования `DocumentError`/`EggpipeError` в exit code.

### M4. `ArtifactWriter.plan` содержит мёртвую ветку и четыре копии `PlannedArtifact`

**Где:** `src/eggpipe/engine/artifact_writer.py:83-202`.

`on_conflict == "error"` уже обработан на строках 137-145, поэтому условие
`if on_conflict == "error" or not force` на строке 183 всегда означает `not force`.
Это не только мёртвый код, но и признак того, что матрица решений размазана по функции.

**Предложение:** вынести решение в маленькие функции:

```python
if not exists:
    return _planned("create", ...)
if _is_owned(...):
    return _owned_action(on_conflict, ...)
if not force:
    return _reject_foreign(...)
return _planned("update", ...)
```

Один конструктор `_planned(action, *, skipped=False)` убирает четыре одинаковых блока.

### M5. `ArtifactWriter.write` смешивает staging, manifest и cleanup

**Где:** `src/eggpipe/engine/artifact_writer.py:204-285`; cleanup-логика повторена в
`clean_manifest` (307-350).

Вложенное условие `if item.path in current_paths or item.skipped` трудно читать, а логика
«оставить/удалить/предупредить» зависит от трёх флагов. Для E6 (глобальный manifest) эту
функцию придётся менять, поэтому риск ошибки высокий.

**Предложение:**

- `_stage_artifacts(plan, staging)`;
- `_new_manifest_entries(plan)`;
- `_cleanup_old_entries(output_dir, old, current_paths, cleanup) -> (entries, diagnostics)`;
- общий `_is_unchanged_owned(path, sha256)` для `write` и `clean_manifest`.

### M6. `plugin_loader` молча проглатывает ошибки форматов и локальных генераторов

**Где:** `src/eggpipe/engine/plugin_loader.py:66-79`, `89-110`.

`load_formats()` при любом исключении делает `continue`; `load_local_generators()` так же
игнорирует ошибки импорта и конструктора. Сломанный плагин выглядит как «плагина нет» —
это дорого в отладке.

**Предложение:** вернуть `(plugins, issues)` по образцу `load_generators_with_issues()`,
переиспользовать `PluginIssue`, а CLI печатать warnings. Для dev-плагинов ошибка импорта
должна быть видимой.

### M7. Проверка format/version в `Composition` повторена четыре раза

**Где:** `src/eggpipe/core/composition.py:77-87`, `195-209`, `232-239`.

Одинаковые пары проверок и одинаковые строки сообщений. При добавлении mixed formats (E3/E4)
это место станет ещё сложнее.

**Предложение:** один helper:

```python
def _ensure_compatible(
    document: ModelDocument,
    *,
    root_format: str | None,
    root_version: str | None,
    path: Path,
) -> None:
```

а `root_format`/`root_version` хранить в `ResolveState` или отдельной `CompositionTarget`.

### M8. Пустой `primitive_types` подменяется встроенными примитивами

**Где:** `src/eggpipe/core/validator.py:34`.

```python
primitives = set(primitive_types or PRIMITIVE_TYPES)
```

Пустое множество — валидное значение контракта «у формата нет примитивов», но из-за
truthiness оно превращается в `PRIMITIVE_TYPES`. Валидация принимает типы, которых у
формата нет.

**Предложение:** различать `None` и пустое множество:

```python
primitives = set(PRIMITIVE_TYPES if primitive_types is None else primitive_types)
```

## Minor

### m1. Дублирование выбора имён в `Composition` и `slicing`

**Где:** `src/eggpipe/core/composition.py:363-382`, `src/eggpipe/core/slicing.py:76-90`.

Две почти одинаковые функции проверки `input.entities/enums/types` с разными текстами
диагностик. **Предложение:** общий helper с параметром `context_label`; сообщения и путь
передавать аргументами.

### m2. Дублирование ignore-наборов discovery и watcher

**Где:** `src/eggpipe/core/discovery.py:13`, `src/eggpipe/watch/watcher.py:14`.

`SKIP_PARTS` и `IGNORED_PARTS` идентичны, а логика «скрытая часть пути» размазана.
**Предложение:** один модуль `core/paths.py` (или константа в discovery) и общий
`is_ignored(path, output_dirs)`.

### m3. `_validate_entity`: пустая ветка и двухпроходная проверка дубликатов

**Где:** `src/eggpipe/core/validator.py:262-292`.

```python
elif field.type in primitives:
    pass
```

Ветка ничего не делает; выше уже вычисляется множество имён, а затем поля перебираются
второй раз. **Предложение:** один проход с `seen_fields`, а неизвестный тип проверять
через `if field.type not in enum_map and field.type not in type_map and field.type not in primitives`.

### m4. `dict[str, Any]` вместо `DiagnosticLocation`

**Где:** `src/eggpipe/core/validator.py:281-286`, `355-359`, `401-407`.

Локация собирается вручную и распаковывается через `**location`. Опечатка в ключе не
будет поймана типами. **Предложение:** `DiagnosticLocation` уже есть; добавить
`error_at(code, message, location)`/`warning_at(...)` и передавать модель.

### m5. 96 литералов диагностик

**Где:** весь `src/eggpipe`, например `MG000` — 13 вхождений.

Коды стабильны и документированы, но строки легко опечатать, а поиск использования
затруднён. **Предложение:** один модуль `eggpipe/diagnostics/codes.py` с константами
`class Code(StrEnum)` (или `MG000 = "MG000"`); это доменный словарь, а не «константа ради
константы». Не переиспользовать коды и не менять их значения.

### m6. `cli.clean`: счётчик называется `removed`, но считает manifests; dry-run берёт lock

**Где:** `src/eggpipe/cli/main.py:543-558`.

`removed += 1` увеличивается на каждый manifest, даже если артефактов не удалили. При
`--dry-run` вызывается `writer.write_lock`, создавая `.eggpipe/lock`. **Предложение:**
`processed_manifests`/`removed_artifacts`; для dry-run не брать write-lock (или сделать
read-only проверку).

### m7. `_print_report` дублирует политику успеха

**Где:** `src/eggpipe/cli/main.py:119-127`.

`success` вычисляется заново по диагностикам и генераторам, хотя `EngineReport` уже содержит
решение. При добавлении новых статусов политики разойдутся. **Предложение:** перенести
strict-политику в `engine/report.py` и использовать один `resolve_exit_code`.

### m8. `Engine._report` и `_has_errors` — дублирование и длинный positional API

**Где:** `src/eggpipe/engine/engine.py:337-354`, `387-388`;
`ArtifactWriter.ExecutionPlan.has_errors` (74-76).

`_has_errors` повторяет `has_errors`; `_report` принимает шесть позиционных аргументов.
**Предложение:** `has_errors(diagnostics)` в `interfaces/diagnostics.py`, а отчёт собирать
через `ReportBuilder`/именованные аргументы.

### m9. `_plugin_version` вводит в заблуждение

**Где:** `src/eggpipe/engine/engine.py:357-358`.

`getattr(plugin, "__version__", "1")` на экземпляре плагина почти всегда даёт `"1"`.
**Предложение:** брать версию distribution/entry point или явно `plugin_version = "unknown"`;
не выдавать api_version за версию плагина.

### m10. `config_show` собирает большой вложенный dict вручную

**Где:** `src/eggpipe/cli/main.py:385-403`.

**Предложение:** Pydantic-модель `ResolvedConfig` или dataclass + `_resolved_config(...)`;
JSON-сериализация станет декларативной.

### m11. `_redact`, `init`-шаблон и `discover()` — мелкие литералы

**Где:** `src/eggpipe/cli/main.py:281-284`, `441-446`;
`src/eggpipe/config/generator_rules.py:84-91`.

Шаблон `.eggpipe.yaml` и маркеры секретов — доменные значения; одноэлементный цикл
`for name in (".eggpipe.yaml",)` лишний. **Предложение:** константы
`DEFAULT_CONFIG_TEMPLATE`, `SECRET_MARKERS`, `CONFIG_FILENAME`.

### m12. `watcher` использует `print` и широкий `except`

**Где:** `src/eggpipe/watch/watcher.py:65-69`.

Ошибка одного пересчёта печатается в stdout, а не в лог/диагностику. **Предложение:**
передавать `on_error` callback или использовать `logging`; `on_any_event` типизировать
как `FileSystemEvent` при наличии watchdog.

### m13. Примеры `metadata.py` используют `Any` и ручную валидацию

**Где:** `examples/tpc-h-generator/src/tpch_generator/metadata.py:23`, `62`.

Для примера допустимо, но `table_info`/`field_sql_type` — кандидаты на маленькие
Pydantic-модели `PostgresTable`/`PostgresField`. Это также упростит E8. **Severity:** Nit
для библиотеки, Minor для примера.

## Nit

- `src/eggpipe/interfaces/formats.py:69` — локальный импорт `validate_entity_model` без
  комментария; цикла нет, можно поднять наверх или объяснить ленивость.
- `src/eggpipe/interfaces/diagnostics.py:33-64` — `error`/`warning` дублируют сборку
  `Diagnostic`; вынести `_diagnostic(level, ...)`.
- `src/eggpipe/core/parser.py:54-55` — мутация входного `raw`; лучше передавать
  нормализованный заголовок явно.
- `src/eggpipe/core/model.py:252-259` — `ModelSlice.formats` пересобирает frozenset на
  каждое обращение; для горячего пути можно кэшировать, но сейчас не критично.
- `src/eggpipe/templating.py:62-69` — словарь опций Jinja2 собирается каждый вызов;
  вынести `DEFAULT_ENVIRONMENT_OPTIONS`.

## Что сделано хорошо

- Доменные модели immutable, входы плагинов не мутируются.
- `core` не импортирует CLI/engine; `Engine` — единственная оркестрация.
- Диагностики структурированы, коды стабильны и документированы.
- `Artifact`, `GenerationResult`, `GeneratorInput` — маленькие и явные контракты.
- Парсер и валидатор разделены; `UNSET` отличает «не задано» от `null`.
- Тесты быстрые, контрактные и golden-тесты покрывают публичное поведение.

## План по приоритетам

1. **Сейчас, до E3:** M8 (пустой `primitive_types`), M6 (видимые ошибки плагинов), M4
   (мёртвая ветка в `plan`). Это небольшие и безопасные исправления.
2. **E3/E4:** M7 (единая проверка format/version) и m1/m2 (общие helpers выбора и путей)
   делать вместе с переработкой форматов и слоёв, чтобы не рефакторить дважды.
3. **E6:** M5 (разделение staging/manifest/cleanup) — обязательная подготовка к глобальному
   manifest.
4. **E7/CLI:** M3/m7 (RunOptions и единая политика exit code) — до добавления JSON v2,
   чтобы отчёт и CLI не разошлись.
5. **Отдельным PR:** m5 (централизация `MGxxx`), m4 (`DiagnosticLocation`), m8/m10/m11.

## Проверенные файлы

`src/eggpipe`: `__init__.py`, `templating.py`, `version.py`, `cli/main.py`,
`config/app_config.py`, `config/generator_rules.py`, `config/logging.py`,
`core/composition.py`, `core/discovery.py`, `core/document.py`, `core/model.py`,
`core/naming.py`, `core/parser.py`, `core/provenance.py`, `core/slicing.py`,
`core/validator.py`, `engine/artifact_writer.py`, `engine/engine.py`,
`engine/format_registry.py`, `engine/plugin_loader.py`, `engine/report.py`,
`interfaces/diagnostics.py`, `interfaces/formats.py`, `interfaces/generator.py`,
`utils/exceptions.py`, `utils/yaml.py`, `watch/watcher.py`;
`examples`: `reference-generator`, `tpc-h-generator` (src).
