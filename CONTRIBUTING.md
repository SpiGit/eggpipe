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

## Локальные hooks

В репозитории лежат git-hooks, которые запускают проверки до коммита и push:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` — быстрые `ruff check` и `ruff format --check`;
- `pre-push` — полный `tools/preflight.py`: типы, тесты, docs, сборка.

Полный прогон вручную:

```bash
uv run python tools/preflight.py
```

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

## Ветки и main

`main` защищён: прямые коммиты и push запрещены. Любое изменение идёт через отдельную
ветку и pull request. Модель ветвления зафиксирована в
[ADR-0015](./engineering/adr/0015-branching-and-release-policy.md): trunk-based,
без постоянной `develop`.

Используй префиксы `feat/`, `fix/`, `docs/`, `chore/`. Для стабилизации или патчей
старой линии допускается временная `release/X.Y`.

```bash
git switch -c type/short-description
# изменения и коммиты
git push -u origin type/short-description
```

Затем открой PR в `main`. Merge разрешён только после зелёных проверок `ci` и `docs`.
Force-push в `main` и удаление ветки `main` запрещены.

PR можно создать через GitHub или локальным helper-скриптом:

```bash
uv run python tools/create_pr.py --title "feat: short description"
```

Скрипт возьмёт токен из `GH_TOKEN` или `~/.config/eggpipe/github-token`,
заполнит «Что изменено» из заголовков коммитов и создаст/обновит PR.

Для соло-разработки достаточно PR без обязательного внешнего approval: проверки CI
и самостоятельный review остаются обязательными.

## Ревью PR

После зелёного `ci-success` запускается независимый ревьюер `pr-reviewer`
(Qwen3.8 Flash). Он возвращает `APPROVE` или `CHANGES REQUESTED`.

- verdict и находки публикуются через `tools/review_pr.py`;
- при замечаниях — правки, повторный CI и одно повторное ревью;
- если второе ревью снова не `APPROVE`, PR остаётся нерешённым, цикл останавливается.

## После merge PR

После подтверждения merge обнови `main` и удали отработавшие ветки:

```bash
git switch main
git fetch --prune origin
git pull --ff-only origin main
git branch -d <branch>
git push origin --delete <branch>
git remote prune origin
```

Для squash-merge проверяй merged PR через GitHub API, а не только
`git branch --merged`.

## Pull request

- Один PR — одна логическая задача.
- Добавляй тесты на новое поведение и запись в `CHANGELOG.md`.
- Не коммить `dist/`, `.venv/`, `.eggpipe/` и сгенерированные артефакты.
- Для изменений публичного API или контрактов плагинов — сначала обнови ТЗ и ADR.
