# Contributing

Спасибо за интерес к `eggpipe`. Проект развивается по ТЗ и System Design, поэтому
изменения должны быть согласованы с документацией.

## Перед началом

1. Прочитай [README](./README.md), [ТЗ](./engineering/requirements/index.md) и
   [System Design](./engineering/system-design/index.md).
2. Проверь принятые решения в [ADR](./engineering/adr/).
3. Для агентов действуют дополнительные правила в [AGENTS.md](./AGENTS.md).

## Окружение

Проект использует Python 3.11+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

`uv.lock` коммитится. Для установки пакета пользователями остаётся `pip install eggpipe`.

Для basedpyright/Pyright в корне есть `pyrightconfig.json`: он задаёт src-layout, `extraPaths` и `.venv`.
Перед проверкой убедитесь, что окружение создано через `uv sync --extra dev`.

## Проверки

Перед pull request:

```bash
uv run ruff check .
uv run ruff format --check src tests tools examples
uv run pyrefly check
uv run pytest --cov
uv run python tools/check_docs.py --strict
uv build
uv run python tools/check_wheel.py dist
```

Все проверки должны проходить. Покрытие ядра — не ниже 80%.

## Документация

- `engineering/requirements/v1.0.md`–`v1.4.md` — история, не редактировать.
- Новое поведение оформляется новой версией ТЗ `vX.Y`, а не правкой текущей.
- Архитектурные решения — новый ADR в `engineering/adr/`, существующие ADR не переписываются.
- При изменении версии обнови `engineering/requirements/index.md`, System Design, README,
  `.session-context.md` и harness-файлы, где указана актуальная версия.

## Pull request

- Один PR — одна логическая задача.
- Добавляй тесты на новое поведение и запись в `CHANGELOG.md`.
- Не коммить `dist/`, `.venv/`, `.eggpipe/` и сгенерированные артефакты.
- Для изменений публичного API или контрактов плагинов — сначала обнови ТЗ и ADR.
