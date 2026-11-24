# Сессии и backlog

Рабочий цикл проекта: как открывать и закрывать сессию, вести backlog и передавать
состояние. Стабильные инварианты для агентов — в [AGENTS.md](../../AGENTS.md),
публичный процесс разработки — в [CONTRIBUTING.md](../../CONTRIBUTING.md), шаблон
закрытия дня — в [day-closure.md](../day-closure.md).

## Термины

| Термин | Смысл |
|--------|-------|
| Сессия | Непрерывный поток работы агента с пользователем над одной задачей |
| PR-цикл | Ветка → PR → CI → ревью → merge → чистка веток |
| Closeout | Перенос `Backlog candidates` в backlog, grooming и архив |
| Handoff | `.session-context.md`: текущее состояние и план |
| День | Рабочий день; закрывается записью в `session-log.md` |

## Инварианты

- Одна сессия — одна задача и один PR-цикл. Исключения — closeout-PR перед плановой
  задачей и PR закрытия дня; больше двух PR задачи на сессию — сигнал разделить сессию.
- `main` меняется только через PR; ветки — `feat/`, `fix/`, `docs/`, `chore/`.
- Backlog: не больше 10 `open`, закрытые записи — в архиве, ID не переиспользуются.
- `CHANGELOG.md` — append-only: конфликты решаются при merge, историю не переписываем.
- `docs/ai` пересобирается при изменении публичного API/CLI и полностью — перед релизом.

## Открытие сессии

Команда: `/session-start`. Шаги:

1. **Модель.** Работа разрешена только на Flash-модели (правило в `AGENTS.md`);
   не-Flash требует явного подтверждения пользователя.
2. **Репозиторий.** `main` обновлён, дерево чистое, handoff и последний PR прочитаны.
3. **PR и CI.** Нет незавершённых PR прошлой сессии; CI на `main` зелёный.
4. **Backlog.** Посчитать `open` и прочитать кандидатов из handoff.
   - `>= 10 open` — сессия начинается с closeout-PR.
   - `< 10 open` — спросить: closeout или плановая задача.
5. **DoR.** Согласовать ADR/design note, owned paths, тестовую матрицу, non-goals.
6. **Варианты.** Предложить 2–3 варианта объёма с рекомендацией.
7. **Имя.** Первым ответом написать `Имя сессии: «<2–5 слов>»` и задать title OpenCode
   через `session_rename`.

## Backlog

- Кандидаты фиксируются только в `Backlog candidates` PR body; в
  [backlog.md](../backlog.md) они попадают на closeout.
- Grooming на closeout: закрыть, слить или явно отложить. При слиянии поглощённый ID
  получает `dropped: включено в B-NNN`, а суть и источник переносятся в активную запись.
- Лимит — 10 `open`; при превышении сначала closeout, потом плановая задача.
- Задача, выросшая до вехи, переносится в [roadmap.md](../roadmap.md); в backlog
  остаётся ссылка. Закрытые записи — в [backlog-archive.md](../backlog-archive.md).

## Ведение сессии

- Owned paths фиксируются до кода; пересечение файлов делает задачи последовательными.
- Shared files (`AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `engineering/backlog.md`,
  `engineering/backlog-archive.md`, `docs/ai/**`, `engineering/requirements/v*.md`)
  редактирует только владелец; при пересечении задачи выполняются последовательно.
- Параллельно — не больше двух сессий/окон; каждая в своём worktree; метки
  `parallel-safe` (нет общих файлов) или `serial` (есть общие файлы).
- Состояние передаётся через `.session-context.md` и `session-log.md`, а не через
  историю чата. Правки handoff не входят в PR задачи: файл коммитится с закрытием дня.

## Ревью

- PR → зелёный `ci` → независимый `pr-reviewer` → публикация вердикта в PR.
- `CHANGES REQUESTED` — только правки по находкам; minor — в `Backlog candidates`.
- Максимум две итерации; после `APPROVE` новых коммитов нет.
- Перед rebase проверить `mergeable_state`; rebase — только при `behind`/`dirty`.

## Закрытие сессии

Команда: `/session-close`. Шаги:

1. Пользователь подтверждает merge; выполняется чистка веток (ниже).
2. Handoff: `.session-context.md` — текущее состояние, ссылка на backlog, план.
3. Closeout: кандидаты → ID, grooming, архив; лимит `open` проверен.
4. Имя сессии: `#<PR> (closed) <задача>`.
5. Ответ: «Сессия закрыта».

После закрытия работа возобновляется только по фразе
«Продолжаем в закрытой сессии: <причина>».

### Чистка веток

```bash
git switch main
git fetch --prune origin
git pull --ff-only origin main
git branch -d <branch>
git push origin --delete <branch>
git remote prune origin
```

Удалять только ветки, которые принадлежат merged PR. Для squash-merge сверяйся со
списком merged PR в GitHub API, а не только с `git branch --merged`; незавершённые и
чужие ветки не трогать.

## Закрытие дня

В конце дня заполнить [session-log.md](../session-log.md) по шаблону
[day-closure.md](../day-closure.md): план, выполнено, вне плана, не выполнено, план на
следующий день. В `.session-context.md` оставить текущее состояние, план на следующий
день и ссылку на backlog; на следующий день — не больше 3–4 задач с импактом.

## Роли файлов

| Файл | Роль | Кто меняет |
|------|------|------------|
| `AGENTS.md` | Стабильные инварианты для агентов | владелец |
| `engineering/process/sessions.md` | Процесс сессий, backlog и handoff | владелец |
| `CONTRIBUTING.md` | Публичный процесс разработки | владелец |
| `.session-context.md` | Handoff: состояние и план | агент сессии, коммит при закрытии дня |
| `engineering/session-log.md` | История сессий и дней | агент сессии |
| `engineering/backlog.md` | Активные задачи `open` | владелец, на closeout |
| `engineering/backlog-archive.md` | Закрытые задачи, append-only | владелец, на closeout |
| `CHANGELOG.md` | Публичная история, append-only | владелец |
| `docs/ai/**` | Generated AI-контекст | владелец |

## Связанные документы

- [AGENTS.md](../../AGENTS.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [Закрытие дня](../day-closure.md)
- [История сессий](../session-log.md)
- [Backlog](../backlog.md)
- [Roadmap](../roadmap.md)
