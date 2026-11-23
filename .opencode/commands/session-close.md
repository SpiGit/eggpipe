---
description: Закрыть рабочую сессию Eggpipe по протоколу
---

Закрой сессию по протоколу [engineering/process/sessions.md](../../engineering/process/sessions.md),
раздел «Закрытие сессии».

1. Дождись подтверждения пользователя, что PR смержен.
2. Выполни чистку веток из раздела «Чистка веток»; удаляй только ветки merged PR.
3. Обнови `.session-context.md`: текущее состояние, ссылка на backlog, план; правки не
   коммить.
4. Выполни backlog closeout: перенеси `Backlog candidates` в
   [engineering/backlog.md](../../engineering/backlog.md), назначь `B-NNN`, проведи
   grooming, перенеси `done`/`dropped` в
   [engineering/backlog-archive.md](../../engineering/backlog-archive.md); проверь лимит
   10 `open`.
5. Если день завершён — заполни [engineering/session-log.md](../../engineering/session-log.md)
   по [day-closure.md](../../engineering/day-closure.md).
6. Переименуй сессию: `#<PR> (closed) <задача>`.
7. Ответь «Сессия закрыта» и напомни, что продолжение — только по фразе
   «Продолжаем в закрытой сессии: <причина>».
