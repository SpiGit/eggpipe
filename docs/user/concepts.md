# Понятия Eggpipe

## Модель

Модель — YAML-документ с заголовком `format`/`version` и секцией `model`:

```yaml
format: entity-model
version: "1.0"
model:
  entities: []
  enums: []
  types: []
```

`entity-model` — встроенный формат. Другие форматы подключаются плагинами.

## Документ, SourceModel, ModelSlice

```text
ModelDocument  →  SourceModel  →  ModelSlice
```

- `ModelDocument` — один YAML-файл: заголовок, imports, model.
- `SourceModel` — результат композиции: union источников и импортов.
- `ModelSlice` — замкнутый срез для конкретного генератора: entities + нужные enums/types.

## Format

Формат определяет:

- какие поля и примитивы допустимы;
- `layer_entity` — схему одного слоя;
- `full_entity` — схему итоговой сущности;
- `extends`/`base_versions` — наследование и версии.

## Model unit и раскладки

| Раскладка | Смысл |
|-----------|-------|
| `monolith` | один файл, несколько сущностей |
| `file-per-model` | один YAML на сущность |
| `directory-per-model` | каталог на модель, несколько слоёв |

В `directory-per-model` файлы-слои образуют цепочку `extends`; базовый слой полный,
дельты валидируются `layer_entity`, итог — `full_entity` самого производного формата.

## Слой и merge

Merge слоёв аддитивный:

- поля — `KEYED`;
- enums/types — `APPEND`;
- metadata — рекурсивно;
- переопределение существующих значений запрещено.

Дубликат формата, несвязанные форматы, конфликт metadata → MG029.

## Срез и closure

`generators[].input` выбирает entities/enums/types. После выбора ядро транзитивно добавляет
все enum/type, на которые ссылаются поля и `CustomType.base`. Неизвестное имя → MG018.

## Ownership и manifest

Артефакт принадлежит location `(generator, output_dir)`, если записан в
`.eggpipe/manifest.json`.

- `--force` перезаписывает только unowned-файл;
- чужой owned-файл не отбирается;
- `cleanup` удаляет только unchanged owned-файлы;
- `skipped: true` не удаляется.

## Плагины

- `@generator` — функция + инъекция `ModelSlice`/`GenerationContext`/`GeneratorConfig`.
- `GeneratorPlugin` — классовый advanced API.
- `FormatPlugin`/`EntityModelFormat` — формат и его схемы.

## Диагностики

Все ошибки и предупреждения — структурированные `Diagnostic` с кодом `MGxxx`.
Warnings можно игнорировать через `diagnostics.ignore` или `--ignore`; errors — нельзя.
