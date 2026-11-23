---
description: Открыть рабочую сессию Eggpipe по протоколу
---

Открой сессию по протоколу [engineering/process/sessions.md](../../engineering/process/sessions.md),
раздел «Открытие сессии».

1. Проверь модель сессии: разрешена только Flash; на не-Flash остановись и спроси
   подтверждение.
2. Проверь репозиторий: `git status --short --branch`, `git log --oneline -8`, последний
   merge в `main`; прочитай `.session-context.md`.
3. Проверь незавершённые PR и CI на `main`.
4. Посчитай `open` в [engineering/backlog.md](../../engineering/backlog.md):
   `>= 10` — сессия начинается с closeout-PR; `< 10` — спроси пользователя, closeout или
   плановая задача.
5. Собери DoR: ADR/design note, owned paths, тестовая матрица, non-goals.
6. Предложи 2–3 варианта объёма с рекомендацией и задай вопросы через `question`.
7. Напиши первым ответом `Имя сессии: «<2–5 слов>»` и задай title через `session_rename`.

Работу не начинай, пока пользователь не выбрал вариант. Отчёт держи коротким:
состояние, backlog count, кандидаты, варианты.
