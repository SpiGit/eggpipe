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
| `--entity` | per-entity генерация: имя или список через запятую, повторяемый флаг; требует `output_scope="entity"` у всех выбранных генераторов |
| `--plugin PATH` | dev-only локальный плагин |
| `--output, -o` | корень артефактов вместо каталога конфига |
| `--var KEY=VALUE` | переменные для плагинов |
| `--dry-run` | показать план без записи |
| `--plan` | расширенный план create/update/skip/delete |
| `--check` | проверить актуальность, exit 1 при drift |
| `--force` | перезаписать unowned-файлы |
| `--strict` | warnings → errors |
| `--ignore` | коды warnings через запятую |
| `--clean` | cleanup enabled для запуска; в per-entity не выполняется (+ Warning EG030) |
| `--incremental` | пропустить parse/validate/generate, если входной fingerprint не менялся; также `EGGPIPE_INCREMENTAL=true`; игнорируется с `--check`/`--force`/`--clean`/`--strict`/`--entity` |
| `--include-disabled` | включить `enabled: false` |
| `--allow-outside-imports` | разрешить импорты/ресурсы вне project root |
| `--output-format` | `text` или `json` |
| `--no-color` | отключить цвет/emoji (также `NO_COLOR`) |
| `--quiet, -q` | только ошибки |
| `--verbose, -v` | подробный вывод |

## watch

```bash
eggpipe watch
eggpipe watch ./models/blog.yaml
```

Флаги как у `generate`, плюс `--debounce-ms` (алиас `--debounce`). `--entity` в watch не поддерживается.
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

| Команда | Флаг | Значение |
|---------|------|----------|
| `config show` | `--show-secrets` | не редактировать секреты в выводе |
| `gen list` | `--all` | показать также плагины с ошибками/несовместимым `api_version` |

### Вывод `gen info`

```text
$ eggpipe gen info reference
id: reference
name: Reference Generator
api_version: 1
input_formats: entity-model
output_scope: model
entry point group: eggpipe.generators
module: reference_generator
class: ReferenceGenerator
```

`module` и `class` показывают, какой объект загружен по entry point: если пакет
установлен не тот, это видно сразу.

### Вывод `format info`

```text
$ eggpipe format info template-model
name: template-model
versions: 1.0
extends: entity-model
primitive_types: bigint,boolean,date,datetime,float,integer,json,string,text,uuid
schemas: 1.0
api_version: 1
module: eggpipe_plugin_template
class: TemplateFormat
base_versions: 1.0->1.0
```

`base_versions` показывает версию базового формата для каждой версии плагина;
`-` — формат не наследует другой формат.

Неизвестный id или имя в `gen info` и `format info` завершается с exit code 2: команда
показывает ближайшие варианты, если они есть, и полный список доступных плагинов.

```text
$ eggpipe format info entity-modell
error: unknown format: entity-modell
did you mean: entity-model
available formats: entity-model
```

### Вывод `format list`

```text
$ eggpipe format list
entity-model	versions=1.0	api_version=1	extends=-	base_versions=-
template-model	versions=1.0	api_version=1	extends=entity-model	base_versions=1.0->1.0
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
| `2` | config/usage/plugin errors, EG033/EG034/EG301/EG302/EG303 |
| `130` | Ctrl+C в `generate`; watch завершается штатно с `0` |

## JSON

```bash
eggpipe generate --output-format json
```

`report_version: 2`; содержит `formats`, `generators[].input_formats`, плоские
`artifacts[].action`, `manifest`, `stale_locations`, `timings`.
