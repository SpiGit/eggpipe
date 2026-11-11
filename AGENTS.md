# AGENTS.md — metadata-generator

Краткое руководство для агентов. Полные требования — в документах ниже; не дублируй их здесь.

## Что это за проект

`metadata-generator` — инструмент, который генерирует артефакты (SQL, Python, TypeScript и т.д.)
из YAML-описания модели данных. Архитектура: нейтральное ядро + плагины генераторов и форматов.

Сейчас репозиторий содержит документацию, harness и ядро v0.1–v0.3: composition, format-плагины,
watch, JSON-отчёт, provenance, writer/manifest/lock, cleanup, `Engine`, CLI, reference-плагин
и golden-тест. Дальше — стабилизация и backlog P1/P2.

## Источники истины

Приоритет при расхождении — сверху вниз:

1. Актуальное ТЗ — файл со статусом **Актуальная** в `docs/requirements/index.md` (сейчас `v1.3.md`):
   поведение, контракты, CLI, запись артефактов.
2. `docs/adr/` — принятые решения (0001 — композиция, 0002 — type checker, 0003 — null-семантика, 0004 — ownership/cleanup, 0005 — library API, 0006 — format extension).
3. `docs/system-design/index.md` — проектирование реализации (классы, потоки, структура).
4. `docs/requirements/index.md` — реестр версий и changelog.
5. `README.md` и `.session-context.md` — краткое состояние проекта.

Если System Design или ADR противоречат ТЗ без ADR-обоснования — это дефект документации. Сообщи
о нём, не меняй смысл требований самостоятельно. Осознанные отклонения фиксируются ADR.

## Карта документов

| Документ | Назначение |
|----------|------------|
| `docs/requirements/` | Актуальное ТЗ и история (статусы — в `index.md`) |
| `docs/system-design/index.md` | System Design |
| `docs/adr/` | Принятые архитектурные решения |
| `docs/reviews/` | Ревью и backlog P1/P2 |
| `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE` | Процесс разработки, история и лицензия |
| `docs/reference/` | Справочники (появятся при реализации) |

## Правила версионирования

- Все версии ТЗ со статусом «Замещена» — история. **Не редактировать.**
- Новое или изменённое поведение оформляется новой версией ТЗ `v1.x`, а не правкой текущей.
- При выпуске версии обнови: ТЗ, `docs/requirements/index.md` (статус + changelog),
  System Design, README и `.session-context.md`.
- ADR не переписываются задним числом. Новое архитектурное решение — новый ADR.
- Диагностические коды `MGxxx` стабильны; не переиспользуй код для другого смысла.

## Защищённые области

- Исторические версии ТЗ (статус «Замещена») — read-only. В `opencode.json` для них стоит `deny`
  на действие `edit` (покрывает `edit`/`write`/`patch`); изменения через shell остаются
  на ответственности агента.
- Не добавляй код реализации, CI и зависимости без явного согласования этапа.
- Не меняй публичный API и контракты плагинов без новой версии ТЗ.
- Не коммить и не push без явного разрешения пользователя.

## Язык и стиль

- Документация и ответы — на русском.
- Код, имена сущностей, пути, флаги CLI и идентификаторы — на английском.
- Термины использовать единообразно: `ModelDocument`, `SourceModel`, `ModelSlice`,
  `FieldDef`, `EnumDef`, `UNSET`, `GeneratorPlugin`, `FormatPlugin`, `GenerationResult`.
- Markdown: заголовки `#`/`##`/`###`, таблицы для перечислений, без emoji.

## Definition of Done

Перед завершением задачи проверь:

- [ ] Изменения согласованы с актуальным ТЗ и не противоречат ADR-0001.
- [ ] Исторические версии ТЗ не изменены.
- [ ] При изменении версии/статуса обновлены `index.md`, System Design, README и `.session-context.md`.
- [ ] Хардкоды актуальной версии в harness (`AGENTS.md`, `.opencode/`, `opencode.json`) синхронизированы;
      прежняя актуальная версия добавлена в `deny`-список.
- [ ] Термины, коды `MGxxx`, флаги CLI и exit codes совпадают во всех документах.
- [ ] `uv run python tools/check_docs.py --strict` проходит без ошибок.
- [ ] `uv run ruff check .`, `uv run ruff format --check src tests tools`, `uv run pyrefly check`
      и `uv run pytest` проходят.
- [ ] `uv build` и `uv run python tools/check_wheel.py dist` проходят.
- [ ] `git diff` просмотрен; в diff нет случайных файлов и переформатирования.
- [ ] Для документации тесты не применимы; для кода — указано, какие проверки запускались.

## Инструменты harness

- Dev/CI используют `uv` и закоммиченный `uv.lock`; для пользователей — `pip`.
- `uv sync --extra dev` — установка dev-окружения.
- `uv run python tools/check_docs.py --strict` — проверка ссылок, версий, harness и терминов.
- `uv run ruff check .` / `uv run ruff format --check src tests tools` — линтер и форматирование.
- `uv run pyrefly check` — строгая проверка типов (Pydantic v2 поддерживается нативно).
- `basedpyright`/Pyright читают `pyrightconfig.json`; основной CI-чекер — Pyrefly.
- `uv run pytest --cov` — тесты и покрытие (порог 80%).
- `uv build` + `uv run python tools/check_wheel.py dist` — сборка и проверка wheel/sdist.
- `/spec-check [фокус]` — read-only проверка согласованности документации.
- `/spec-release <версия>` — подготовка новой версии ТЗ и синхронизация документов.
- `/adr-new <название>` — создание нового ADR по шаблону.
- Skill `spec-consistency` — чек-лист кросс-документной проверки.
- Skill `plugin-contract` — контракты плагинов и публичный API.
- Subagent `spec-reviewer` — независимое read-only ревью документации.
