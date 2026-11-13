# Конфигурация `.eggpipe.yaml`

Конфиг обязателен для CLI-команд, которые работают с sources и generators. Формат модели
в конфиге не задаётся — он определяется YAML-файлами модели.

## Верхний уровень

```yaml
version: "1.0"
defaults:
  naming_convention: snake_case
variables:
  env: dev
diagnostics:
  stale_dates: false
  ignore: [EG015]
resources:
  - path: ./shared/templates
  - path: ./shared/seed.json
    as: seed
sources: []
generators: []
```

| Поле | Обязательно | Назначение |
|------|-------------|------------|
| `version` | да | версия схемы конфига, сейчас `"1.0"` |
| `defaults.naming_convention` | нет | подсказка плагинам |
| `variables` | нет | строковые переменные для `GenerationContext` |
| `diagnostics.stale_dates` | нет | EG014 для `file-per-model` |
| `diagnostics.ignore` | нет | коды warnings, которые нужно скрыть |
| `resources` | нет | общие ресурсы относительно каталога конфига |
| `sources` | да для генерации | модели |
| `generators` | да для генерации | генераторы и output dirs |

## Sources

```yaml
sources:
  - path: ./model.yaml
    layout: monolith

  - path: ./models
    layout: file-per-model
    files: ["*.yaml"]

  - path: ./models-layered
    layout: directory-per-model
    model_dirs: ["*"]
    files: ["*.yaml"]
    models:
      customer:
        files: [base.yaml, postgres.yaml]
        resources: [templates/card.html, assets/**]
    input:
      entities: [Customer]
      enums: []
      types: []
```

| Поле | monolith | file-per-model | directory-per-model |
|------|----------|----------------|---------------------|
| `path` | файл | каталог | каталог |
| `files` | запрещён | обязателен | обязателен |
| `model_dirs` | запрещён | запрещён | обязателен |
| `models` | запрещён | запрещён | опционален |
| `input` | да | да | да |

`files`/`model_dirs` — точные имена или glob (`*`, `**`, `?`, `[...]`).

## Generators

```yaml
generators:
  - id: oracle-ddl
    enabled: true
    output_dir: ./generated/oracle
    on_conflict: overwrite   # overwrite | skip | error
    cleanup: off             # off | prompt | enabled
    input:
      entities: [User, Post]
      enums: [PostStatus]
      types: []
    options: {}
```

- `id` — id плагина; должен совпадать с entry point.
- `output_dir` — относительный путь от каталога конфига (или от `-o`).
- `input` пустой = все entities/enums/types.
- `options` валидирует плагин.

## Resources

```yaml
resources:
  - path: ./shared/templates
  - path: ./shared/fixtures/seed.json
    as: seed
```

- Путь или glob; каталог разворачивается рекурсивно.
- `as` допустим только для одного файла.
- Alias по умолчанию — путь без расширения; для модели — `<model_dir>/<path>`.
- Коллизия alias → EG032.
- Ресурсы попадают в `GenerationContext.imports`.

## Input и closure

`input` фильтрует модель после композиции. Пустое значение означает «все». После выбора
ядро добавляет transitively все enum/type, на которые ссылаются поля. Неизвестное имя →
EG018.

## Переменные

```bash
eggpipe generate --var env=prod --var token=secret
```

CLI имеет приоритет над `variables` в конфиге. Все значения строковые. Секреты
редактируются в `config show`, если не указан `--show-secrets`.
