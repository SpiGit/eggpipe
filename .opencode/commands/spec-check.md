---
description: Проверить согласованность документации Eggpipe
agent: spec-reviewer
---

Проведи read-only проверку согласованности документации `Eggpipe`.

Фокус проверки: $ARGUMENTS

Обязательно прочитай:

- `AGENTS.md`
- `docs/requirements/index.md`
- актуальное ТЗ (файл со статусом «Актуальная»)
- `docs/system-design/index.md`
- `docs/adr/0001-composition-merge-semantics.md`
- `README.md`

Проверь:

1. Термины: `ModelDocument`, `SourceModel`, `ModelSlice`, `FieldDef`, `EnumDef`, `UNSET`.
2. Публичный API и контракты плагинов (список из ТЗ §6.2, System Design §2).
3. Диагностические коды `MGxxx`, их диапазоны и смысл.
4. CLI-команды, флаги и exit codes (0 / 1 / 2 / 130).
5. Правила путей, ownership, manifest и cleanup.
6. Версии и статусы в `docs/requirements/index.md` и README.
7. Противоречия между ТЗ, System Design и ADR-0001.

Ограничения: ничего не редактируй. Shell, webfetch и websearch запрещены; используй только `read`, `glob`, `grep`.

Формат ответа:

- **Critical** — противоречия, ломающие контракт или поведение.
- **Major** — неполные или устаревшие места.
- **Minor** — стиль, терминология, ссылки.

Для каждой находки: `file:line`, цитата, проблема, предлагаемое исправление.
Если находок нет — перечисли проверенные разделы и подтверди согласованность.
