# TPC-H example

Показательный пример для `metadata-generator`: стандартная схема TPC-H из 8 таблиц и плагины,
которые генерируют PostgreSQL DDL и Pydantic v2 модели.

## Структура

```text
examples/tpc-h/
  model/                 # entity-model, file-per-entity
  .mg.yaml               # один генератор tpch
  .mg.split.yaml         # tpch-ddl + tpch-pydantic
  expected/              # golden-артефакты
```

Модель использует `metadata.postgres` для SQL-специфики:

```yaml
metadata:
  postgres:
    table: region
    primary_key: [r_regionkey]

# field
metadata:
  postgres:
    type: char(25)
```

`foreign_keys` задаются на уровне entity:
```yaml
metadata:
  postgres:
    foreign_keys:
      - columns: [n_regionkey]
        references:
          table: region
          columns: [r_regionkey]
```

## Установка и запуск

```bash
uv pip install -e examples/tpc-h-generator

# Один генератор: DDL + Pydantic
mg generate -c examples/tpc-h/.mg.yaml

# Split-вариант
mg generate -c examples/tpc-h/.mg.split.yaml
```

Артефакты:

- `generated/postgres/schema.sql` — `CREATE TABLE`, PK, FK;
- `generated/python/tpch_models.py` — Pydantic v2 модели с `Decimal`, `date`, `Field(max_length=...)`.

## Варианты

| Вариант | Что показывает |
|---------|----------------|
| `tpch` | Один `GeneratorPlugin` выпускает несколько артефактов |
| `tpch-ddl` + `tpch-pydantic` | Раздельные генераторы и общий `output_dir` |

Один и тот же `model/` используется всеми генераторами: генератор-специфичные настройки
живут в `.mg.yaml`, а технологическая специфика — в `metadata.postgres` сущности или поля.

Pydantic-модели плоские: только колонки; PK/FK остаются в DDL.

## Шаблоны

Генераторы используют Jinja2-шаблоны из `examples/tpc-h-generator/src/tpch_generator/templates/`
через `metadata_generator.templating` (extra `[jinja]`).

Свой каталог можно передать через `options.templates_dir`:

```yaml
generators:
  - id: tpch
    output_dir: ./generated
    options:
      schema: public
      templates_dir: ./templates
```
