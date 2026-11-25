# Backlog

Конкретные отложенные задачи. Roadmap задаёт направления и вехи, здесь — мелкие
улучшения, технический долг и follow-up после ревью.

## Правила

- Каждый отложенный minor получает ID `B-NNN`; ID стабильны и не переиспользуются.
- Статусы записей: `open` (активная), `done`, `dropped` (с причиной).
- Активная таблица содержит только `open`; записи `done`/`dropped` переносятся в
  [архив](./backlog-archive.md) на Backlog closeout.
- Запись содержит источник, суть и импакт.
- При закрытии заполняются PR/дата; для `dropped` причина пишется в «Задача» с префиксом
  `dropped:`. При слиянии записей поглощённый ID получает `dropped: включено в B-NNN`,
  а суть и источник переносятся в поглотившую запись.
- Если задача вырастает до отдельной вехи, она переносится в `roadmap.md`, а здесь
  остаётся ссылка.
- Ревьюер только сообщает находки; автор PR фиксирует minor в `Backlog candidates` PR body,
  а в этот файл он попадает на Backlog closeout.
- Перед новой фичей backlog groomится: закрыть, слить или явно отложить записи; держать
  не больше 10 открытых.

## Записи

| ID | Статус | Задача | Источник | Импакт | PR | Дата |
|----|--------|--------|----------|--------|----|------|
| B-025 | open | Docs accuracy sweep (остаток P2 audit 2026-11-18): v2.1 refs, ADR legacy, терминология, format API; уточнить в отчёте аудита, что P2 закрываются после 0.4.0; устранить дубли числовых и политических правил (`10 open`, `3–4 задач`, формат `dropped:`) — один источник; обновить устаревшие таблицу «Документы проекта» и сводную шапку (`0.4.0`, ТЗ v2.4) в `session-log.md` и дату/текущую точку в `roadmap.md`; drift `docs/ai` (`context.md` gen list vs `manifest.json`, ссылка на отсутствующий cookbook); нет поля `cache` в `docs/user/api/index.md`; макет `format list` в `engineering/decisions/eggpipe.md` расходится с реальным выводом; ADR-0022, формулировки: «вне код-фенсов» в §2.4 верно только для `.md`, у `opencode.json` и workflows фенсов нет — уточнить, §3 перечисляет «замещённые версии ТЗ», тогда как allowlist накрывает и актуальное ТЗ (§2.3) — выровнять примеры; ADR-0023 §1, стиль: «действовать на живые документы» → «действует для живых документов». Узкий срез (шапки ADR на ТЗ v2.5, freshness `docs/ai`, `plugins.md` в llms-full) закрыт PR #94 | audit report, PR #43/#46/#49/#77/#78/#82/#84/#98/#101/#102 review | Документация без stale-оговорок, дублей и неверных примеров; `check_docs --strict` зелёный | — | — |
| B-043 | open | `preflight --stamp`: `SKIP_PARTS` матчит `build`/`site`/`dist` на любой глубине, не включает `.hypothesis`/`.ruff_cache`; temp-stamp не чистится; нет теста «без `--stamp` stamp не создаётся»; пунктуация в `CONTRIBUTING.md`; окружение не входит в хеш. Watch: узкая гонка «прорвавшегося» после cancel таймера в `_Debouncer`; в `cli.md` не указан exit 130 при Ctrl+C во время первичной генерации; `run_watch(max_delay_ms=...)` не используется тестами; CLI-тесты debounce зависят от `.env` в CWD; малый запас интервала в coalescing-тесте. Reviewer permissions: shell-маска `uv run python tools/review_pr.py *` допускает любые аргументы (`--body-file` из репозитория, чужой `--pr`) — сузить или задокументировать остаточный риск; защита файла пакета от перезаписи; паритет масок секретов у `pr-reviewer`/`spec-reviewer`; probe-пути покрывают только прямых детей `/tmp/opencode/`; зафиксировать fnmatch-модель (`*` через `/`) тестом или комментарием; шире покрыть `.env`-семейство | PR #61/#65, #94 review | Ложные пропуски/лишние прогоны, устойчивость watch и тестов | — | — |
| B-048 | open | Document cache: эффективность, документация и тесты — переиспользовать raw YAML между discovery/fingerprint/parse/`remember` (A2); discovery без полного `load_yaml` ради `format` (A1); кэшировать `config_dir.resolve()`; общий atomic-JSON helper вместо дубля `_write_json_atomic`; path-free guard покрывает документы с imports; `CacheEntry.inputs` и рекурсивная closure в System Design; spike §6-C (происхождение 29–53 %), §8 (`--entity`), §9 (комментарии текстом); уточнить `entries`/`bytes` («состояние `.eggpipe/cache/`» vs `docs/*.json`); строка матрицы ADR-0021 о ресурсе в input-closure; CHANGELOG `[Unreleased]`: `cache_version` 2 при фактической 3 | PR #72, #74/#75/#78, #82/#84 review | Меньше разборов, дублирования и расхождений в документации | — | — |
| B-056 | open | Тест глубокой вложенности: глубину брать от `sys.getrecursionlimit()` вместо фиксированных 2000 (`test_deeply_nested_meta_is_miss_and_recovers`, `test_deeply_nested_payload_is_miss`) | PR #91 review | Тест не зависит от нестандартного лимита рекурсии | — | — |
| B-058 | open | Structured logging, формулировки: CHANGELOG — события кэша не несут `duration_ms` (уточнить фразу); ТЗ §8.8 и System Design — «без абсолютных путей» относится к `message`, а не только `extra`; CHANGELOG #96 — `relative_text` «сокращает все вхождения базы» (уточнить фразу); оформить при следующей версии ТЗ | PR #93, #96 review | Однозначный контракт логов | — | — |
| B-059 | open | Benchmark/test hygiene: `EngineReport.model_construct` в тестах обходит валидацию — собирать валидный отчёт; `_measure_noop`/`_measure_changed` возвращают `reports[-1]` и падают при `iterations=0` — добавить guard или тест; `tests/test_logging.py`: лишние скобки в сравнении `relative_text(...) == ("model/base.yaml: model/base.yaml")` — вынести ожидание в переменную, чтобы `ruff format` не возвращал скобки | PR #93, #96 review | Тесты ближе к реальным данным и читаемее | — | — |
| B-061 | open | `check_docs`/tooling polish: `_write_text` без `newline="\n"` (CRLF на Windows); тихий skip freshness в dependency-free job — явное сообщение или документирование; DOC170 не указывает место расхождения; нет регресс-гейта на шапки ADR при смене версии ТЗ (DOC121); DOC171 не упомянут в `AGENTS.md`; дублирование конфига в тестах | PR #94 review | Предсказуемая сборка `docs/ai` и явные ошибки | — | — |
| B-064 | open | `AGENTS.md`: перечень ADR в карте документов заканчивается на 0021 — добавить ADR-0022/0023 и синхронизировать список | PR #101 review | Актуальная карта ADR для агентов | — | — |
