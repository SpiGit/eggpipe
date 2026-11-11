# TPC-H example generators

Пример плагинов-генераторов для `metadata-generator`:

- `tpch` — один генератор, выпускает PostgreSQL DDL и Pydantic v2 модели;
- `tpch-ddl` / `tpch-pydantic` — split-вариант двумя генераторами.

Модель — стандартные 8 таблиц TPC-H: `region`, `nation`, `part`, `supplier`, `partsupp`,
`customer`, `orders`, `lineitem`. Один и тот же набор YAML используется всеми генераторами.

## Установка

```bash
uv pip install -e examples/tpc-h-generator
```

После установки генераторы доступны через entry points:

```bash
mg gen list
```

## Запуск

```bash
# Один генератор: DDL + Pydantic
mg generate -c examples/tpc-h/.mg.yaml

# Split: два независимых генератора
mg generate -c examples/tpc-h/.mg.split.yaml
```

Артефакты по умолчанию пишутся в `examples/tpc-h/generated/`.
