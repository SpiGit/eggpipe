# TPC-H example generators

Пример плагинов-генераторов для `eggpipe`:

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
eggpipe gen list
```

## Запуск

```bash
# Один генератор: DDL + Pydantic
eggpipe generate -c examples/tpc-h/.eggpipe.yaml

# Split: два независимых генератора
eggpipe generate -c examples/tpc-h/.eggpipe.split.yaml
```

Артефакты по умолчанию пишутся в `examples/tpc-h/generated/`.
