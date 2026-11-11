# Contributing

Спасибо за интерес к `metadata-generator`. Проект развивается по ТЗ и System Design, поэтому
изменения должны быть согласованы с документацией.

## Перед началом

1. Прочитай [README](./README.md), [ТЗ](./docs/requirements/index.md) и
   [System Design](./docs/system-design/index.md).
2. Проверь принятые решения в [ADR](./docs/adr/).
3. Для агентов действуют дополнительные правила в [AGENTS.md](./AGENTS.md).

## Окружение

Проект использует Python 3.11+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

`uv.lock` коммитится. Для установки пакета пользователями остаётся `pip install metadata-generator`.

Для basedpyright/Pyright в корне есть `pyrightconfig.json`: он задаёт src-layout, `extraPaths` и `.venv`.
Перед проверкой убедитесь, что окружение создано через `uv sync --extra dev`.

## Проверки

Перед pull request:

```bash
uv run ruff check .
uv run ruff format --check src tests tools
uv run pyrefly check
uv run pytest --cov
uv run python tools/check_docs.py --strict
uv build
uv run python tools/check_wheel.py dist
```

Все проверки должны проходить. Покрытие ядра — не ниже 80%.

## Документация

- `docs/requirements/v1.0.md` и `v1.1.md` — история, не редактировать.
- Новое поведение оформляется новой версией ТЗ `v1.x`, а не правкой текущей.
- Архитектурные решения — новый ADR в `docs/adr/`, существующие ADR не переписываются.
- При изменении версии обнови `docs/requirements/index.md`, System Design, README,
  `.session-context.md` и harness-файлы, где указана актуальная версия.

## Pull request

- Один PR — одна логическая задача.
- Добавляй тесты на новое поведение и запись в `CHANGELOG.md`.
- Не коммить `dist/`, `.venv/`, `.mg/` и сгенерированные артефакты.
- Для изменений публичного API или контрактов плагинов — сначала обнови ТЗ и ADR.
