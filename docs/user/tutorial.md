# Tutorial: TPC-H от модели до артефактов

Пошаговый пример на реальном TPC-H: восемь таблиц, directory-per-model и два способа
запуска генераторов. Пример лежит в `examples/tpc-h` и `examples/tpc-h-generator`.

## 1. Установка

```bash
uv sync --extra dev
uv pip install -e examples/tpc-h-generator
```

Проверьте, что генераторы видны:

```bash
eggpipe gen list
eggpipe format list
```

## 2. Структура модели

```text
examples/tpc-h/
├── model/
│   ├── customer/base.yaml
│   ├── lineitem/base.yaml
│   ├── nation/base.yaml
│   ├── orders/base.yaml
│   ├── part/base.yaml
│   ├── partsupp/base.yaml
│   ├── region/base.yaml
│   └── supplier/base.yaml
├── .eggpipe.yaml
├── .eggpipe.split.yaml
└── expected/
```

Каждый каталог — одна модель (`directory-per-model`). Внутри `base.yaml` — одна сущность.

## 3. Конфигурация

`.eggpipe.yaml`:

```yaml
version: "1.0"
sources:
  - path: ./model
    layout: directory-per-model
    model_dirs: ["*"]
    files: ["*.yaml"]
generators:
  - id: tpch
    output_dir: ./generated
    options:
      schema: public
diagnostics:
  ignore: [EG015]
```

- `model_dirs: ["*"]` — все каталоги моделей.
- `files: ["*.yaml"]` — слои внутри каждой модели.
- `tpch` — один генератор, выпускает DDL и Pydantic-модели.

## 4. Проверка и план

```bash
eggpipe model validate examples/tpc-h/model/customer/base.yaml
eggpipe generate -c examples/tpc-h/.eggpipe.yaml --plan
```

`--plan` не пишет файлы и не меняет manifest.

## 5. Генерация

```bash
eggpipe generate -c examples/tpc-h/.eggpipe.yaml
```

Результат:

```text
examples/tpc-h/generated/
├── postgres/schema.sql
└── python/tpch_models.py
```

Либо split-вариант с двумя генераторами:

```bash
eggpipe generate -c examples/tpc-h/.eggpipe.split.yaml
```

Оба варианта дают одинаковые `expected/schema.sql` и `expected/tpch_models.py`.

## 6. Проверка актуальности

```bash
eggpipe generate -c examples/tpc-h/.eggpipe.yaml --check
```

При drift или отсутствии файла команда завершится exit code 1 и ничего не запишет.

## 7. Manifest и очистка

```bash
cat examples/tpc-h/.eggpipe/manifest.json
eggpipe clean -c examples/tpc-h/.eggpipe.yaml --dry-run
eggpipe clean -c examples/tpc-h/.eggpipe.yaml --yes
```

Manifest хранит locations `(generator, output_dir)`, хэши артефактов и `skipped`.
Удаляются только unchanged owned-файлы.

## 8. Что дальше

- [Понятия](concepts.md) — model unit, слой, срез, ownership.
- [Конфигурация](configuration.md) — все поля `.eggpipe.yaml`.
- [Плагины](plugins.md) — как написать свой генератор.
- [API](api/index.md) — запуск через `Engine`.
