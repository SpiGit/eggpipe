# AGENTS.md — eggpipe

Краткое руководство для агентов. Полные требования — в документах ниже; не дублируй их здесь.

## Что это за проект

`eggpipe` — инструмент, который генерирует артефакты (SQL, Python, TypeScript и т.д.)
из YAML-описания модели данных. Архитектура: нейтральное ядро + плагины генераторов и форматов.

Репозиторий содержит реализацию ТЗ v2.2: composition, форматы и слои, decorator API,
watch, JSON-отчёт v2, provenance, глобальный manifest/lock, cleanup, `Engine`, CLI,
reference- и TPC-H-плагины, golden-тесты. Дальше — E9: CI, версия пакета и release.

## Источники истины

Приоритет при расхождении — сверху вниз:

1. Актуальное ТЗ — файл со статусом **Актуальная** в `engineering/requirements/index.md` (сейчас `v2.2.md`):
   поведение, контракты, CLI, запись артефактов.
2. `engineering/adr/` — принятые решения (0001 — композиция, 0002 — type checker, 0003 — null-семантика, 0004 — ownership/cleanup, 0005 — library API, 0006 — format extension, 0007 — наследование форматов, 0008 — model units/раскладки, 0009 — глобальный manifest, 0010 — decorator API, 0011 — публичный API v2 и идентичность, 0012 — English-only source, 0013 — EG-коды, 0014 — beta-статус и совместимость до 1.0).
3. `engineering/system-design/index.md` — проектирование реализации (классы, потоки, структура).
4. `engineering/requirements/index.md` — реестр версий и changelog.
5. `README.md` и `.session-context.md` — краткое состояние проекта.

Если System Design или ADR противоречат ТЗ без ADR-обоснования — это дефект документации. Сообщи
о нём, не меняй смысл требований самостоятельно. Осознанные отклонения фиксируются ADR.

## Карта документов

| Документ | Назначение |
|----------|------------|
| `engineering/requirements/` | Актуальное ТЗ и история (статусы — в `index.md`) |
| `engineering/system-design/index.md` | System Design |
| `engineering/adr/` | Принятые архитектурные решения |
| `engineering/reviews/` | Ревью и backlog P1/P2 |
| `engineering/decisions/eggpipe.md` | Имя, CLI/конфиг, бренд и идеи лого |
| `docs/user/plugins.md` | Руководство по плагинам |
| `engineering/release.md` | Релизный чек-лист |
| `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE` | Процесс разработки, история и лицензия |
| `docs/user/` | Пользовательская документация и справочники |
| `docs/ai/` | Компактный контекст и задачи для AI-агентов |
| `engineering/` | ТЗ, ADR, System Design, ревью, план, релиз |

## Правила версионирования

- Все версии ТЗ со статусом «Замещена» — история. **Не редактировать.**
- Новое или изменённое поведение оформляется новой версией ТЗ `vX.Y`, а не правкой текущей.
- При выпуске версии обнови: ТЗ, `engineering/requirements/index.md` (статус + changelog),
  System Design, README и `.session-context.md`.
- ADR не переписываются задним числом. Новое архитектурное решение — новый ADR.
- Диагностические коды `EGxxx` стабильны; не переиспользуй код для другого смысла.

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
- [ ] Термины, коды `EGxxx`, флаги CLI и exit codes совпадают во всех документах.
- [ ] `uv run python tools/check_docs.py --strict` проходит без ошибок.
- [ ] При изменении публичного API/CLI пересобран `docs/ai` (`tools/build_ai_docs.py`).
- [ ] `uv run ruff check .`, `uv run ruff format --check src tests tools examples`, `uv run pyrefly check`
      и `uv run pytest` проходят.
- [ ] `uv build` и `uv run python tools/check_wheel.py dist` проходят.
- [ ] `git diff` просмотрен; в diff нет случайных файлов и переформатирования.
- [ ] Для документации тесты не применимы; для кода — указано, какие проверки запускались.

## Инструменты harness

- Dev/CI используют `uv` и закоммиченный `uv.lock`; для пользователей — `pip`.
- `uv sync --extra dev` — установка dev-окружения.
- `uv run python tools/check_docs.py --strict` — проверка ссылок, версий, harness и терминов.
- `uv run python tools/build_ai_docs.py` — пересборка `docs/ai` (llms, manifest, schemas, diagnostics).
- `uv run ruff check .` / `uv run ruff format --check src tests tools examples` — линтер и форматирование.
- `uv run pyrefly check` — строгая проверка типов (Pydantic v2 поддерживается нативно).
- `basedpyright`/Pyright читают `pyrightconfig.json`; основной CI-чекер — Pyrefly.
- `uv run pytest --cov` — тесты и покрытие (порог 80%).
- `uv build` + `uv run python tools/check_wheel.py dist` — сборка и проверка wheel/sdist.
- `/spec-check [фокус]` — read-only проверка согласованности документации.
- `/spec-release <версия>` — подготовка новой версии ТЗ и синхронизация документов.
- `/adr-new <название>` — создание нового ADR по шаблону.
- Skill `spec-consistency` — чек-лист кросс-документной проверки.
- Skill `plugin-contract` — контракты плагинов и публичный API.
- Skill `clean-code` — принципы чистого кода и чек-лист code review.
- Skill `python-patterns` — паттерны, антипаттерны и решающее дерево рефакторинга.
- Subagent `spec-reviewer` — независимое read-only ревью документации.
