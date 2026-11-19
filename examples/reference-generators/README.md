# Reference generators

Четыре небольших генератора на decorator API — SQL, Pydantic v2, TypeScript и OpenAPI.
Пример показывает, как один `ModelSlice` превращается в артефакты для разных стеков.

## Что внутри

```text
examples/reference-generators/
├── pyproject.toml
├── src/eggpipe_reference_generators/   # _common, sql, pydantic_models, typescript, openapi
└── tests/test_contract.py
```

Все генераторы объявлены через `@generator(...)`; `output_scope` по умолчанию —
`model`. Пример требует `eggpipe>=0.4.0`: contract-тесты проверяют `output_scope`. Генераторы возвращают
`list[Artifact]` и не пишут файлы сами: записью занимается ядро.

| Генератор `id` | Артефакт |
|----------------|----------|
| `sql` | `schema.sql` |
| `pydantic` | `models.py` |
| `typescript` | `models.ts` |
| `openapi` | `openapi.json` |

## Установка

Из корня репозитория:

```bash
pip install -e examples/reference-generators
eggpipe gen list
```

Или через `uv`:

```bash
uv pip install -e examples/reference-generators
```

В `eggpipe gen list` появятся `sql`, `pydantic`, `typescript` и `openapi`.

## Модель

`model.yaml`:

```yaml
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
        - name: email
          type: string
          required: true
        - name: createdAt
          type: datetime
          nullable: true
  types:
    - name: Email
      base: string
```

## Конфигурация

`.eggpipe.yaml`:

```yaml
version: "1.0"
sources:
  - path: ./model.yaml
    layout: monolith
generators:
  - id: sql
    output_dir: ./out
  - id: pydantic
    output_dir: ./out
  - id: typescript
    output_dir: ./out
  - id: openapi
    output_dir: ./out
```

## Запуск

```bash
eggpipe generate
```

В `./out` появятся `schema.sql`, `models.py`, `models.ts` и `openapi.json`.
Таблица маппинга типов, примеры вывода и ограничения — в cookbook:
[docs/user/cookbook/reference-generators.md](../../docs/user/cookbook/reference-generators.md).

## Детерминизм

Сущности сортируются по имени, поля сохраняют порядок объявления, JSON пишется с
`sort_keys=True`, каждый артефакт заканчивается переводом строки. Поэтому вывод подходит
для `eggpipe generate --check` в CI.

## Тесты

```bash
uv run pytest examples/reference-generators/tests -q
```

Тесты проверяют контракт каждого генератора (`validate_generator_contract`), имена
артефактов, базовое содержимое, детерминизм двух прогонов, изоляцию `config.options`
и регистрацию entry points. Для последнего примера должен быть установлен:
`uv pip install -e examples/reference-generators`.

## Ограничения

- DDL без первичных ключей, индексов и внешних ключей.
- Значения `default` не выводятся; enum-поля маппятся в строку.
- Идентификаторы `sql`, `pydantic`, `typescript`, `openapi` могут конфликтовать с
  генераторами приложения.
