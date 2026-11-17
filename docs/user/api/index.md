# API Reference

Публичный API — `eggpipe.__init__`. Всё из `core.*` и `engine.*` считается внутренним.

## Engine

```python
from eggpipe import AppConfig, Engine, ProjectConfigLoader

rules = ProjectConfigLoader().load(".eggpipe.yaml")
engine = Engine(AppConfig(), rules)

plan = engine.build()                  # без записи
report = engine.generate()             # build + запись
report = engine.check()                # проверка drift без записи
plan = engine.build(incremental=True)  # opt-in кэш на один вызов
report = engine.generate(entities=["User"])  # per-entity generate
```

`Engine` не вызывает `sys.exit`, не настраивает root-logger и не пишет файлы в `build()`.
`AppConfig(incremental=True)` включает кэш, `build(incremental=...)` переопределяет настройку;
`check()` всегда работает без кэша. `entities=[...]` включает per-entity режим для генераторов
с `output_scope="entity"`.

Полезные параметры `Engine`:

```python
Engine(
    AppConfig(),
    rules,
    config_dir=Path("."),
    generators={"my-generator": MyGenerator()},
    formats=FormatRegistry(),
    variables={"env": "dev"},
)
```

## EngineReport

```python
report.success: bool
report.exit_code: int
report.diagnostics: list[Diagnostic]
report.formats: list[FormatSummary]
report.generators: list[GeneratorReport]
report.artifacts: list[ArtifactReport]
report.manifest: ManifestSummary | None
report.stale_locations: list[StaleLocation]
report.timings: dict[str, int]
```

`artifacts[].action`: `create | update | skip | delete | conflict | error | drift`.
`generators[].status`: `ok | error | skipped`.

## Provenance

`git_provenance(path)` запускает `git` и наследует окружение процесса. Если вызывающий код
работает под git hook или CI с `GIT_DIR`/`GIT_WORK_TREE`, он должен очистить `GIT_*` перед
вызовом; harness делает это в `tools/preflight.py`. Вне git-репозитория функция возвращает
`None`.

## Исключения

- `EggpipeError` — базовая ошибка библиотеки.
- `DocumentError` — YAML/модель/формат; несёт `code` (`EGxxx`).
- `ConfigValidationError` — конфиг/usage.
- `FormatConflictError`, `FormatInheritanceError`, `UnknownFormatError`.
- `PluginContractError` — EG301/EG302.
- `ArtifactPathError`, `ManifestError`, `LockError`.

Ошибки генераторов не выбрасываются наружу: они попадают в `GenerationResult.errors`
или `EngineReport.diagnostics`.

## Плагины

- [Generator API](generator.md) — `@generator` и `GeneratorPlugin`.
- [Format API](format.md) — `FormatPlugin` и `EntityModelFormat`.
- [Модели](models.md) — `Entity`, `FieldDef`, `ModelSlice`, `UNSET`, `Diagnostic`.
