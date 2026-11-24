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
| B-025 | open | Закрыть P2 из audit 2026-11-18 (v2.1 refs, ADR legacy, терминология, format API); `docs/user/plugins.md` в `LLMS_FULL_SOURCES` и freshness-проверка `docs/ai`; уточнить в отчёте аудита, что P2 закрываются после 0.4.0; устранить дубли числовых и политических правил (`10 open`, `3–4 задач`, формат `dropped:`) — один источник; обновить устаревшие таблицу «Документы проекта» в `session-log.md` и дату/текущую точку в `roadmap.md` | audit report, PR #43/#46/#77/#78 review | Документация без stale-оговорок и дублей | — | — |
| B-036 | open | `troubleshooting.md`: подсказка про `gen list --all`; уточнить формулировку CHANGELOG (подсказка только при полной неудаче загрузки) | PR #52 review | DX при сломанных плагинах | — | — |
| B-037 | open | Изоляция тестов: инлайновые `fake_entry_points` не фильтруют группу (`tests/test_cli.py`, 8 мест; `tests/test_plugin_loader.py`, 7 из 9) — перевести на общий хелпер; reference-примеры — фильтровать `issues` по id примера (общий venv), cookbook — «перед запуском установите пример» (B-038) | PR #52/#53 review | Тесты не изолируют чужие группы; хрупкость в общем окружении | — | — |
| B-040 | open | Оформить ADR о политике версий в документации (`DOC161`, allowlist, `bump_version.py`); критерий — правило действует шире релиза | PR #51 review | Зафиксировать решение | — | — |
| B-042 | open | `engineering/decisions/eggpipe.md`: макет `format list` расходится с реальным выводом | PR #49 review | Документ идей вводит в заблуждение | — | — |
| B-043 | open | `preflight --stamp`: `SKIP_PARTS` матчит `build`/`site`/`dist` на любой глубине, не включает `.hypothesis`/`.ruff_cache`; temp-stamp не чистится; нет теста «без `--stamp` stamp не создаётся»; пунктуация в `CONTRIBUTING.md`; окружение не входит в хеш. Watch: узкая гонка «прорвавшегося» после cancel таймера в `_Debouncer`; в `cli.md` не указан exit 130 при Ctrl+C во время первичной генерации; `run_watch(max_delay_ms=...)` не используется тестами; CLI-тесты debounce зависят от `.env` в CWD; малый запас интервала в coalescing-тесте (B-045) | PR #61/#65 review | Ложные пропуски/лишние прогоны, устойчивость watch и тестов | — | — |
| B-048 | open | Document cache: эффективность — переиспользовать raw YAML между discovery/fingerprint/parse/`remember` (A2); discovery без полного `load_yaml` ради `format` (A1); кэшировать `config_dir.resolve()`; общий atomic-JSON helper вместо дубля `_write_json_atomic` | PR #72, #74/#75 review | Меньше разборов и дублирования | — | — |
| B-049 | open | Document cache: документация и тесты — path-free guard покрывает документы с imports; `CacheEntry.inputs` и рекурсивная closure в System Design; статус L2 в ТЗ v2.4 (§11.1, §14) и System Design §5.1 привести к ADR-0020 (сейчас «L2/L3 — future» противоречит SD §9.3); spike §6-C (происхождение 29–53 %), §8 (`--entity`), §9 (комментарии текстом) | PR #72/#74/#78 review | Точность документации и покрытия | — | — |
| B-050 | open | ТЗ v2.5: метрики hits/misses кэша; публикация формата `.eggpipe/cache/`; актуальный `eggpipe_version` в примере manifest (B-041); пакет с roadmap 0.5.0 п. 3 | PR #46/#47/#73 review | Единый пакет изменений ТЗ | — | — |
| B-051 | open | Document cache hardening, раунд 2: `_meta_state()` ловит `RecursionError` (глубоко вложенный `meta.json` сейчас роняет прогон) и тест на него; унифицировать наборы исключений в `remember()`/`_meta_state()`; усилить тесты: зафиксировать причину промаха в `test_deeply_nested_payload_is_miss`, тест `RecursionError` из `restore_document`, assert `entity("User") is not None` | PR #79 review | Битый `meta.json` не роняет прогон, единое правило для недоверенного кэша | — | — |
