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
| B-025 | open | Docs accuracy sweep: закрыть P2 из audit 2026-11-18 (v2.1 refs, ADR legacy, терминология, format API); `docs/user/plugins.md` в `LLMS_FULL_SOURCES` и freshness-проверка `docs/ai`; уточнить в отчёте аудита, что P2 закрываются после 0.4.0; устранить дубли числовых и политических правил (`10 open`, `3–4 задач`, формат `dropped:`) — один источник; обновить устаревшие таблицу «Документы проекта» в `session-log.md` и дату/текущую точку в `roadmap.md`; stale «действующие контракты — ТЗ v2.4» в ADR-0001, 0007–0010, 0017–0020; drift `docs/ai` (`context.md` gen list vs `manifest.json`, ссылка на отсутствующий cookbook); нет поля `cache` в `docs/user/api/index.md`; макет `format list` в `engineering/decisions/eggpipe.md` расходится с реальным выводом | audit report, PR #43/#46/#49/#77/#78/#82/#84 review | Документация без stale-оговорок, дублей и неверных примеров; критерий готовности — ни одной stale-ссылки на ТЗ v2.4 в ADR, `docs/ai` и пользовательских примерах, `check_docs --strict` зелёный | — | — |
| B-040 | open | Оформить ADR о политике версий в документации (`DOC161`, allowlist, `bump_version.py`); критерий — правило действует шире релиза | PR #51 review | Зафиксировать решение | — | — |
| B-043 | open | `preflight --stamp`: `SKIP_PARTS` матчит `build`/`site`/`dist` на любой глубине, не включает `.hypothesis`/`.ruff_cache`; temp-stamp не чистится; нет теста «без `--stamp` stamp не создаётся»; пунктуация в `CONTRIBUTING.md`; окружение не входит в хеш. Watch: узкая гонка «прорвавшегося» после cancel таймера в `_Debouncer`; в `cli.md` не указан exit 130 при Ctrl+C во время первичной генерации; `run_watch(max_delay_ms=...)` не используется тестами; CLI-тесты debounce зависят от `.env` в CWD; малый запас интервала в coalescing-тесте | PR #61/#65 review | Ложные пропуски/лишние прогоны, устойчивость watch и тестов | — | — |
| B-048 | open | Document cache: эффективность, документация и тесты — переиспользовать raw YAML между discovery/fingerprint/parse/`remember` (A2); discovery без полного `load_yaml` ради `format` (A1); кэшировать `config_dir.resolve()`; общий atomic-JSON helper вместо дубля `_write_json_atomic`; path-free guard покрывает документы с imports; `CacheEntry.inputs` и рекурсивная closure в System Design; spike §6-C (происхождение 29–53 %), §8 (`--entity`), §9 (комментарии текстом); уточнить `entries`/`bytes` («состояние `.eggpipe/cache/`» vs `docs/*.json`); строка матрицы ADR-0021 о ресурсе в input-closure; CHANGELOG `[Unreleased]`: `cache_version` 2 при фактической 3 | PR #72, #74/#75/#78, #82/#84 review | Меньше разборов, дублирования и расхождений в документации | — | — |
| B-053 | open | Harness: сузить `edit`/`read` pr-reviewer до `/tmp/opencode/pr-*.md`; DOC146 проверять итоговый эффект с учётом поздних `allow`; уточнить формулировки «Не проверено» и случай непереданных критериев | PR #83/#85 review | Точные права и однозначный вердикт | — | — |
| B-054 | open | Logging: абсолютные пути в debug-сообщениях при JSON-режиме; `_escape` для `\n`/`\r`; привязать `run_id`/`event`/`duration_ms` к логам движка; policy-тест «без секретов и абсолютных путей» | PR #84 review | Инварианты structured logging | — | — |
| B-055 | open | Benchmark follow-ups (#88 review): убрать лишний `_generate(...)` перед циклом в `_measure_noop`/`_measure_changed` (`report` переприсваивается в первой итерации); переименовать подпись заполненного `CacheReport` в `test_render_contains_rows` с `"no-op"` на `"changed"` | PR #88 review | Меньше лишних прогонов и яснее тест | — | — |
| B-056 | open | Тест глубокой вложенности: глубину брать от `sys.getrecursionlimit()` вместо фиксированных 2000 (`test_deeply_nested_meta_is_miss_and_recovers`, `test_deeply_nested_payload_is_miss`) | PR #91 review | Тест не зависит от нестандартного лимита рекурсии | — | — |
