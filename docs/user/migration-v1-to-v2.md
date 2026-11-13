# Migration: v1.x → v2.x

До первого публичного релиза обратная совместимость не гарантируется. Основные изменения:

## Имена

| v1.x | v2.x |
|------|------|
| `metadata_generator` | `eggpipe` |
| `mg` | `eggpipe` |
| `.mg.yaml` | `.eggpipe.yaml` |
| `.mg/` | `.eggpipe/` |
| `metadata_generator.generators` | `eggpipe.generators` |
| `metadata_generator.formats` | `eggpipe.formats` |
| `MG_*` env | `EGGPIPE_*` |

## Источники и раскладки

- `layout` обязателен: `monolith`, `file-per-model`, `directory-per-model`.
- Для `file-per-model` и `directory-per-model` обязателен `files`.
- Для `directory-per-model` обязателен `model_dirs`.
- `models.<dir>` переопределяет `files`/`resources`.

## Модель

- `version` формата опционален; без него берётся latest.
- В одном запуске допускаются разные форматы.
- `Entity.format`/`format_version`/`layer_sources`, `FieldDef.source`.
- `GenerationContext.formats` вместо `format`/`format_version`.

## Плагины

- `input_formats` обязателен для каждого генератора.
- Основной API — `@generator`; классовый `GeneratorPlugin` остаётся advanced.
- `Artifact`/`GenerationResult`/`Diagnostic` — без изменений по смыслу.
- Несовместимый формат — MG033, exit 2.

## Manifest

- Per-generator `output_dir/.eggpipe/manifests` удалён.
- Глобальный `.eggpipe/manifest.json`, `manifest_version: 2`.
- Locations `(generator, output_dir)`.
- `--force` не отбирает файл у другого location.
- `eggpipe clean` работает без конфига и плагинов.

## JSON-отчёт

- `report_version: 2`.
- `artifacts[].action`, `generators[].status`.
- `formats`/`input_formats`, `manifest`, `stale_locations`, `timings`.

## Что проверить после обновления

```bash
eggpipe config validate
eggpipe generate --plan
eggpipe generate
eggpipe generate --check
```

Старые `.mg/` каталоги можно удалить: manifest v1 не поддерживается.
