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

## Локальная настройка git

```bash
git config rerere.enabled true
git config merge.conflictstyle zdiff3
```

`rerere` переиспользует разрешённые конфликты, `zdiff3` показывает их компактнее.

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
Он также предупреждает, если hand-written diff превышает бюджет; осознанное
исключение фиксируется флагом `--allow-large "reason"`.

Для соло-разработки достаточно PR без обязательного внешнего approval: проверки CI
и самостоятельный review остаются обязательными.

## Подготовка PR

До кода должны быть согласованы:

- ADR или короткий design note;
- матрица инвалидации/отключения для кэша или аналогичных механизмов;
- изменения публичного API и CLI;
- тестовая матрица;
- список затрагиваемых файлов и non-goals.

Бюджет PR:

- до 500 hand-written строк;
- до 15 файлов;
- generated/full-copy не считаются: `docs/ai/**`, `engineering/requirements/v*.md`,
  `uv.lock`.

Если изменение больше — дели на stacked PR: spec/ADR, реализация, синхронизация
документации. Один PR — одна логическая задача.

В описании PR указывай карту ревью: что смотреть в первую очередь, какие файлы
generated, какие вопросы задать ревьюеру и что вне scope. Блок `<!-- pr-size:... -->`
обновляет `tools/create_pr.py`, вручную его не редактируй.

## Параллельная работа

Независимые задачи можно вести параллельно, если у них нет общих файлов.

- Одна задача — одна ветка и один worktree.
- Для каждой задачи зафиксируй owned paths.
- Общие файлы (`AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `engineering/backlog.md`,
  `docs/ai/**`, `engineering/requirements/v*.md`) обновляет один владелец или они
  меняются последовательно.
- Generated-файлы пересобирает только владелец задачи.
- Перед merge проверяй `mergeable_state`; rebase — только при `behind`/`dirty`.
- При пересечении файлов задачи становятся последовательными.

## Закрытие дня

В конце дня заполни `engineering/session-log.md` по шаблону
[`engineering/day-closure.md`](./engineering/day-closure.md): план, выполнено, вне плана,
не выполнено, план на следующий день. В `.session-context.md` оставь текущее состояние,
план на следующий день и ссылку на `engineering/backlog.md`. На следующий день — не больше
3–4 задач с импактом.

## Ревью PR

После зелёного `ci-success` запускается независимый ревьюер `pr-reviewer`
(Qwen3.8 Flash). Он возвращает `APPROVE` или `CHANGES REQUESTED`.

- verdict и находки публикуются через `tools/review_pr.py`;
- при замечаниях — только правки по находкам, повторный CI и одно повторное ревью;
- после правок запусти `uv run python tools/create_pr.py`: блок размера обновится,
  body и карта ревью сохранятся;
- minor и «заодно улучшим» фиксируются в `engineering/backlog.md` или follow-up PR;
- если второе ревью снова не `APPROVE`, PR не уходит в третью итерацию: оставшаяся
  работа делится на меньшие PR;
- после `APPROVE` новых коммитов не добавляется;
- перед rebase проверь `mergeable_state`: `clean` — мержить без rebase, rebase только при
  `behind`/`dirty`; WIP-коммиты squash-ить перед rebase;
- секция `## Size exception` персистентна: `create_pr.py` сохраняет её при обновлении PR,
  убрать можно только ручным редактированием body.

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
