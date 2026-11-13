# API Reference

Публичный API — `eggpipe.__init__`. Всё из `core.*` и `engine.*` считается внутренним.

## Engine

```python
from eggpipe import AppConfig, Engine, GeneratorRulesLoader

rules = GeneratorRulesLoader().load(".eggpipe.yaml")
engine = Engine(AppConfig(), rules)

plan = engine.build()       # без записи
report = engine.generate()  # build + запись
report = engine.check()     # проверка drift без записи
```

`Engine` не вызывает `sys.exit`, не настраивает root-logger и не пишет файлы в `build()`.

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

## Исключения

- `EggpipeError` — базовая ошибка библиотеки.
- `DocumentError` — YAML/модель/формат; несёт `code` (`MGxxx`).
- `ConfigValidationError` — конфиг/usage.
- `FormatConflictError`, `FormatInheritanceError`, `UnknownFormatError`.
- `PluginContractError` — MG301/MG302.
- `ArtifactPathError`, `ManifestError`, `LockError`.

Ошибки генераторов не выбрасываются наружу: они попадают в `GenerationResult.errors`
или `EngineReport.diagnostics`.

## Плагины

- [Generator API](generator.md) — `@generator` и `GeneratorPlugin`.
- [Format API](format.md) — `FormatPlugin` и `EntityModelFormat`.
- [Модели](models.md) — `Entity`, `FieldDef`, `ModelSlice`, `UNSET`, `Diagnostic`.
