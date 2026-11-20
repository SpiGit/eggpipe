# AGENTS.md — eggpipe

Краткое руководство для агентов. Полные требования — в документах ниже; не дублируй их здесь.

## Что это за проект

`eggpipe` — инструмент, который генерирует артефакты (SQL, Python, TypeScript и т.д.)
из YAML-описания модели данных. Архитектура: нейтральное ядро + плагины генераторов и форматов.

Репозиторий содержит реализацию ядра и спецификацию ТЗ v2.4: composition, форматы и слои, decorator API,
watch, JSON-отчёт v2, provenance, глобальный manifest/lock, cleanup, `Engine`, CLI,
reference- и TPC-H-плагины, golden-тесты. Per-entity генерация реализована: `output_scope`, `Engine.build/generate/check(entities=...)`, CLI `--entity` (ADR-0018).

## Источники истины

Приоритет при расхождении — сверху вниз:

1. Актуальное ТЗ — файл со статусом **Актуальная** в `engineering/requirements/index.md` (сейчас `v2.4.md`):
   поведение, контракты, CLI, запись артефактов.
2. `engineering/adr/` — принятые решения (0001 — композиция, 0002 — type checker, 0003 — null-семантика, 0004 — ownership/cleanup, 0005 — library API, 0006 — format extension, 0007 — наследование форматов, 0008 — model units/раскладки, 0009 — глобальный manifest, 0010 — decorator API, 0011 — публичный API v2 и идентичность, 0012 — English-only source, 0013 — EG-коды, 0014 — beta-статус и совместимость до 1.0, 0015 — ветвление и релизная политика, 0016 — политика deprecation, 0017 — инкрементальная генерация, 0018 — per-entity генерация).
3. `engineering/system-design/index.md` — проектирование реализации (классы, потоки, структура).
4. `engineering/requirements/index.md` — реестр версий; полный changelog — `changelog.md`.
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
| `engineering/backlog.md` | Отложенные minor и технический долг |
| `engineering/day-closure.md` | Шаблон и правила завершения дня |
| `engineering/roadmap.md` | Направления развития и подготовка к 1.0 |
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
- Не начинай задачи следующей вехи, пока текущий релиз не выпущен. Если задача следующей
  вехи смержена раньше, перенеси её в текущий релиз и убери из будущей вехи.
- При выпуске версии обнови: ТЗ, `engineering/requirements/index.md` (статусы),
  `engineering/requirements/changelog.md` (запись),
  System Design, README и `.session-context.md`.
- ADR не переписываются задним числом. Новое архитектурное решение — новый ADR.
- Диагностические коды `EGxxx` стабильны; не переиспользуй код для другого смысла.

## Защищённые области

- `main` защищён: прямые коммиты и push запрещены. Изменения — через отдельную ветку и pull request.
- Исторические версии ТЗ (статус «Замещена») — read-only. В `opencode.json` для них стоит `deny`
  на действие `edit` (покрывает `edit`/`write`/`patch`); изменения через shell остаются
  на ответственности агента.
- Не добавляй код реализации, CI и зависимости без явного согласования этапа.
- Не меняй публичный API и контракты плагинов без новой версии ТЗ.
- Не коммить и не push без явного разрешения пользователя.

## Подготовка PR

- **Definition of Ready:** до кода согласованы ADR/design note, матрица инвалидации или
  отключения, изменения публичного API/CLI, тестовая матрица, список файлов и non-goals.
- **Бюджет размера:** до 500 hand-written строк и до 15 файлов. Generated/full-copy не
  считаются: `docs/ai/**`, `engineering/requirements/v*.md`, `uv.lock`. Больше — stacked PR.
- **Один PR — одна логическая задача.** Для большой фичи разделяй spec/ADR, реализацию и
  синхронизацию документации; не смешивай их в одном diff.
- **Карта ревью в PR body:** что смотреть в первую очередь, какие файлы generated и их
  можно не читать построчно, какие вопросы задать ревьюеру, что вне scope. Блок
  `<!-- pr-size:... -->` обновляет `create_pr.py`, вручную его не редактируй.
- `tools/create_pr.py` предупреждает о превышении бюджета; `--allow-large "reason"`
  фиксирует осознанное исключение.

## Сессии и контекст

- Одна сессия — одна задача или один день. Не держи одну сессию на несколько дней:
  контекст переотправляется на каждом шаге и растёт вместе с историей.
- Передача состояния — через `.session-context.md` (текущее состояние и план) и
  `engineering/session-log.md` (история), а не через историю чата.
- В начале сессии читай `.session-context.md`, `engineering/backlog.md` и только нужные
  документы, а не весь `engineering/`.
- Большие файлы читай диапазонами (`sed -n`, `grep`), не целиком; агентам без shell —
  диапазоны через `read` (`offset`/`limit`).
- Промпт ревью — пакет: diff, список изменённых файлов и критерии приёмки; ревьюер
  не читает репозиторий целиком.

## Параллельная работа

- Правила owned paths, shared files и generated-файлов — в `CONTRIBUTING.md`,
  раздел «Параллельная работа».
- `CHANGELOG.md`, `engineering/backlog.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/ai/**` и
  `engineering/requirements/v*.md` редактирует только владелец; при пересечении задачи
  выполняются последовательно.
- Subagent работает в отдельном worktree; основной агент координирует порядок merge.
- Если owned paths пересекаются, задачи выполняются последовательно.

## Закрытие дня

В конце дня заполнить `engineering/session-log.md` по шаблону
[`engineering/day-closure.md`](./engineering/day-closure.md): план, выполнено, вне плана,
не выполнено, план на следующий день. В `.session-context.md` оставить текущее состояние,
план на следующий день и ссылку на `engineering/backlog.md`. На следующий день — не больше
3–4 задач с импактом. Backlog closeout: `Backlog candidates` из PR body переносятся в
`engineering/backlog.md` одним PR.

## PR review

1. Создать PR и дождаться `ci-success`.
2. Убедиться, что `HEAD` запушен, и передать subagent `pr-reviewer` (Qwen3.8 Flash)
   пакет ревью: diff, список изменённых файлов и «Критерии приёмки» из PR body.
   Номер PR нужен только для публикации ревью.
3. Опубликовать verdict и находки:
   ```bash
   uv run python tools/review_pr.py --pr <N> --body "<verdict и находки>"
   ```
   Для своего PR используется `event=COMMENT`: GitHub не позволяет формально
   approve собственный PR.
4. Если verdict `CHANGES REQUESTED` — внести **только правки по находкам**. Minor и
   «заодно улучшим» выноси в раздел `Backlog candidates` PR body (backlog правится только
   на Backlog closeout) или follow-up PR, чтобы не менять уже проверенный diff. После
   правок запустить `uv run python tools/create_pr.py`: он обновит блок размера и сохранит
   body; карту ревью обновить, если изменился scope.
5. Максимум две итерации. Если второе ревью снова не `APPROVE`, не запускать третье:
   разделить оставшуюся работу на меньшие PR и сообщить о нерешённом PR.
6. После `APPROVE` новых коммитов не добавлять; любое изменение требует нового ревью.
7. Перед rebase проверить `mergeable_state`: `clean` — мержить без rebase; rebase только
   при `behind`/`dirty`. WIP-коммиты squash-ить перед rebase.

## После merge PR

Когда пользователь подтверждает, что PR смержен:

1. Переключиться на `main`:
   ```bash
   git switch main
   ```
2. Забрать актуальное состояние и удалить исчезнувшие remote-ветки:
   ```bash
   git fetch --prune origin
   git pull --ff-only origin main
   ```
3. Удалить локальные ветки, чьи PR уже merged. Для squash-merge нельзя полагаться
   только на `git branch --merged`: сверяйся со списком merged PR в GitHub API.
4. Удалить соответствующие remote-ветки:
   ```bash
   git push origin --delete <branch>
   ```
5. Выполнить `git remote prune origin` и проверить `git status`.

Удалять только ветки, которые принадлежат merged PR. Незавершённые и чужие ветки
не трогать.

## Контекст

- Не читай весь `engineering/` без необходимости: начинай с `engineering/index.md`.
- ADR открывай по теме, исторические ТЗ — только если задача про историю.
- `.session-context.md` содержит только текущее состояние; история сессий — в
  `engineering/session-log.md`.
- Полный changelog требований — `engineering/requirements/changelog.md`, реестр версий —
  `engineering/requirements/index.md`.

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
- [ ] При изменении версии/статуса обновлены `index.md`, `requirements/changelog.md`, System Design, README и `.session-context.md`.
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
- `uv run python tools/bump_version.py <version>` — подготовка релиза (версия, CHANGELOG, docs/ai).
- `uv run python tools/build_ai_docs.py` — пересборка `docs/ai` (llms, manifest, schemas, diagnostics).
- `uv run ruff check .` / `uv run ruff format --check src tests tools examples` — линтер и форматирование.
- `uv run pyrefly check` — строгая проверка типов (Pydantic v2 поддерживается нативно).
- `basedpyright`/Pyright читают `pyrightconfig.json`; основной CI-чекер — Pyrefly.
- `uv run pytest --cov` — тесты и покрытие (порог 80%).
- `uv build` + `uv run python tools/check_wheel.py dist` — сборка и проверка wheel/sdist.
- `/spec-check [фокус]` — read-only проверка согласованности документации.
- `/spec-release <версия>` — подготовка новой версии ТЗ и синхронизация документов.
- `/adr-new <название>` — создание нового ADR по шаблону.
- `uv run python tools/create_pr.py` — создать/обновить PR из текущей ветки (нужен `GH_TOKEN`).
- `uv run python tools/benchmark.py` — базовый бенчмарк TPC-H.
- `uv run python tools/review_pr.py` — опубликовать review-комментарий в PR (нужен `GH_TOKEN`).
- Subagent `pr-reviewer` — независимое ревью PR на Qwen3.8 Flash.
- Skill `spec-consistency` — чек-лист кросс-документной проверки.
- Skill `plugin-contract` — контракты плагинов и публичный API.
- Skill `clean-code` — принципы чистого кода и чек-лист code review.
- Skill `python-patterns` — паттерны, антипаттерны и решающее дерево рефакторинга.
- Subagent `spec-reviewer` — независимое read-only ревью документации.
