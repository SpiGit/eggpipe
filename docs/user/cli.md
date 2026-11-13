# CLI reference

## Команды

```text
eggpipe generate [MODELS...] [OPTIONS]
eggpipe watch [MODELS...] [OPTIONS]
eggpipe init [PATH] --layout LAYOUT
eggpipe config show|validate|schema
eggpipe model validate MODELS...
eggpipe model schema [--format NAME] [--version V]
eggpipe gen list [--all]|info ID
eggpipe format list|info NAME
eggpipe clean [--dry-run] [--yes] [--root PATH]
```

## generate

```bash
eggpipe generate
eggpipe generate ./models/blog.yaml
eggpipe generate ./models/a.yaml ./models/b.yaml -g oracle-ddl
eggpipe generate -g oracle-ddl
```

| Флаг | Значение |
|------|----------|
| `--config, -c` | путь к `.eggpipe.yaml` |
| `--generator, -g` | id генераторов: через запятую или повторно |
| `--plugin PATH` | dev-only локальный плагин |
| `--output, -o` | корень артефактов вместо каталога конфига |
| `--var KEY=VALUE` | переменные для плагинов |
| `--dry-run` | показать план без записи |
| `--plan` | расширенный план create/update/skip/delete |
| `--check` | проверить актуальность, exit 1 при drift |
| `--force` | перезаписать unowned-файлы |
| `--strict` | warnings → errors |
| `--ignore` | коды warnings через запятую |
| `--clean` | cleanup enabled для запуска |
| `--include-disabled` | включить `enabled: false` |
| `--allow-outside-imports` | разрешить импорты/ресурсы вне project root |
| `--output-format` | `text` или `json` |
| `--quiet, -q` | только ошибки |
| `--verbose, -v` | подробный вывод |

## watch

```bash
eggpipe watch
eggpipe watch ./models/blog.yaml
```

Флаги как у `generate`, плюс `--debounce-ms` (алиас `--debounce`).
Первичная генерация выполняется сразу; изменения конфига перезагружают настройки,
плагины — нет.

## init

```bash
eggpipe init --layout monolith
eggpipe init --layout file-per-model
eggpipe init --layout directory-per-model
```

Создаёт `.eggpipe.yaml` и пример модели. В non-tty `--layout` обязателен.

## config / model / gen / format

```bash
eggpipe config show
eggpipe config validate
eggpipe config schema

eggpipe model validate ./model.yaml
eggpipe model schema
eggpipe model schema --format postgres-model --version 2.0

eggpipe gen list --all
eggpipe gen info tpch

eggpipe format list
eggpipe format info entity-model
```

## clean

```bash
eggpipe clean --dry-run
eggpipe clean --yes
eggpipe clean --root ./project
```

Работает только по глобальному `.eggpipe/manifest.json`, без загрузки плагинов.
Удаляет unchanged owned-файлы и пустые locations.

## Exit codes

| Код | Значение |
|-----|----------|
| `0` | успех |
| `1` | errors парсинга/валидации/генерации, drift, `--strict` warnings |
| `2` | config/usage/plugin errors, EG033/EG034/EG301/EG302 |
| `130` | Ctrl+C в `generate`; watch завершается штатно с `0` |

## JSON

```bash
eggpipe generate --output-format json
```

`report_version: 2`; содержит `formats`, `generators[].input_formats`, плоские
`artifacts[].action`, `manifest`, `stale_locations`, `timings`.
