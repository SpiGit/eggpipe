# Backlog archive

Закрытые записи backlog (`done`/`dropped`). Активные задачи — [backlog.md](./backlog.md).

## Правила

- Архив append-only: записи не редактируются задним числом; допустимо только исправление
  ссылок и опечаток.
- ID стабильны и не переиспользуются. Поглощённый при слиянии ID остаётся `dropped` со
  ссылкой на поглотившую запись, а его суть и источник перенесены в активную запись.
- Строки `open` в архив не попадают.

## Записи

| ID | Статус | Задача | Источник | Импакт | PR | Дата |
|----|--------|--------|----------|--------|----|------|
| B-001 | done | create_pr: не терять хвост body при открытом size-блоке | PR #28 review | Потеря карты ревью | #28 | 2026-11-17 |
| B-002 | done | тест сохранения title/body при обновлении PR | PR #28 review | Регрессия заголовка | #28 | 2026-11-17 |
| B-003 | done | перейти на `numstat -z` | PR #28 review | Устойчивость к путям | #28 | 2026-11-17 |
| B-004 | done | тест передачи `clean_env` в preflight | PR #28 review | Изоляция от GIT_* | #28 | 2026-11-17 |
| B-005 | done | документировать окружение `git_provenance` | PR #29 review | Поведение публичной функции | #29 | 2026-11-17 |
| B-006 | done | убрать остатки v2.2 из session-log | PR #29 review | Историческая запись | #29 | 2026-11-17 |
| B-007 | done | уточнить формулировки day-closure | PR #29 review | Меньше двусмысленности | #29 | 2026-11-17 |
| B-008 | done | зафиксировать персистентность `Size exception` | PR #29 review | Пользователь не знает, как убрать секцию | #29 | 2026-11-17 |
| B-009 | done | уточнить `input_paths` при невалидном model | PR #29 review | Контракт формата | #29 | 2026-11-17 |
| B-010 | done | явный `return None` в `_disable_incremental` | PR #28 review | Читаемость | #28 | 2026-11-17 |
| B-011 | done | колонка статуса в «Закрытых» | PR #29 review | Правило и таблица | #29 | 2026-11-17 |
| B-012 | done | роль автора и ревьюера | PR #29 review | Роль read-only ревьюера | #29 | 2026-11-17 |
| B-013 | done | чекбокс «minor нет» в PR-шаблоне | PR #29 review | Безусловный чекбокс | #29 | 2026-11-17 |
| B-014 | done | ссылка на backlog из roadmap | PR #29 review | Навигация | #29 | 2026-11-17 |
| B-015 | done | рубрика CHANGELOG для backlog | PR #29 review | Keep a Changelog | #29 | 2026-11-17 |
| B-016 | done | ссылка на backlog в day-closure | PR #29 review | Единообразие ссылок | #29 | 2026-11-17 |
| B-017 | done | формулировка EG018 | PR #29 review | Противоречие «пусто = все» | #29 | 2026-11-17 |
| B-018 | done | EG303 в user diagnostics | PR #29 review | Каталог кодов | #29 | 2026-11-17 |
| B-019 | done | ссылка ADR-0018 в System Design | PR #29 review | Навигация | #29 | 2026-11-17 |
| B-020 | done | `output_scope` в skill | PR #29 review | Чек-лист | #29 | 2026-11-17 |
| B-021 | done | `--clean --entity`: warning EG030 вместо тихого игнора | PR #26 review | Пользователь не видит, что cleanup пропущен | #32 | 2026-11-17 |
| B-022 | done | исправить таблицы v2.4 | PR #29 review | Мелкие дефекты | #29 | 2026-11-17 |
| B-023 | done | PR body: показывать число тестов и покрытие (`Tests: N; coverage: X%`) | user request 2026-11-17 | Видимость coverage в PR | #38 | 2026-11-18 |
| B-024 | done | тесты merge `formats`/`generated_at` в per-entity manifest | PR #32 review | Закрыть пробел покрытия | #37 | 2026-11-18 |
| B-026 | done | CLI info: `format list` показывает `api_version`/`extends`/`base_versions`; убрать dead `getattr(plugin, "base_versions", {})`; в `cli.md` указать, что did-you-mean работает для `gen info` и `format info`; покрыть тестами пустой список доступных и отсутствие близких совпадений | PR #41 review | Полная картина плагинов, точные docs и тесты | #49 | 2026-11-19 |
| B-027 | done | Plugin discovery DX: подсказка `gen list --all` при пустом списке; общий тестовый хелпер фильтрует entry points по группе (инлайновые моки — B-037) | PR #41 review | Путаница при сломанных плагинах | #52 | 2026-11-19 |
| B-028 | dropped | dropped: `gen info --plugin PATH` перенесён в roadmap 0.6.0 — требует новой версии ТЗ | PR #41 review | Отладка плагина до установки | #48 | 2026-11-19 |
| B-029 | done | Reference-примеры: `test_contract.py` читает `plugin.output_scope` напрямую и падает на eggpipe 0.3.2 из PyPI — перейти на `getattr` или поднять зависимость; путь в `pyrightconfig.json`; ссылка в корневом `README.md`; формулировка snake_case/PascalCase в cookbook; пустая сущность в SQL; тесты discovery, generic id и `config.options` | PR #42 review | Совместимость, docs и покрытие примеров | #53 | 2026-11-19 |
| B-030 | dropped | dropped: включено в B-029 | PR #42 review | — | #48 | 2026-11-19 |
| B-031 | done | Contract errors: код для ошибок времени декорирования; вынести `_describe_generator_location` в общий внутренний модуль; hint-литералы — в константы | PR #43 review | Непоследовательный вывод, дублирование | #56 | 2026-11-20 |
| B-032 | dropped | dropped: включено в B-025 | PR #43 review | — | #48 | 2026-11-19 |
| B-033 | dropped | dropped: включено в B-026 | PR #41 review | — | #48 | 2026-11-19 |
| B-034 | done | Пост-релизные правки docs: дубль `create_pr.py` в CHANGELOG и порядок секций; версия в примерах `system-design` §8/§12; stale «0.3.2» в шапке `session-log.md`; раздел аудита в roadmap §5; состав 0.5.0 без benchmarks; пример `major.minor` в `release.md` | PR #45–#47 review | Читаемость заметок, доверие к примерам | #50 | 2026-11-19 |
| B-035 | done | `bump_version.py`: покрыть тестами `main()`/`--dry-run` и ветки ошибок; включить скрипт и его тест в `REQUIRED_FILES` | PR #51 review | Регрессии релизного скрипта | #57 | 2026-11-20 |
| B-038 | dropped | dropped: включено в B-037 | PR #53 review | — | #76 | 2026-11-24 |
| B-039 | done | `release.md`: иллюстрация `major.minor` (`1.2`) и примеры путей `/0.3/`, `/0.4/` рассогласованы; `DOC161` называть «проверкой», а не «правилом» | PR #51 review | Единообразие документации | #58 | 2026-11-20 |
| B-041 | dropped | dropped: включено в B-050 | PR #46/#47 review | — | #76 | 2026-11-24 |
| B-044 | done | Minor ревью ADR-0019: ссылка на ADR-0019 в списке `README.md`; в ADR §4 убрать строку «`adr/index.md` — статус принято» (уже выполнена #63); в §3.1–3.2 явно записать подавление `trigger()`/re-trigger после стоп-сигнала; в §6 уточнить «~3.3 s сверх длительности прогона»; титул в `adr/index.md` дословно как заголовок файла | PR #63 review | Единообразие ADR/README, однозначность design note | #65 | 2026-11-20 |
| B-045 | dropped | dropped: включено в B-043 | PR #65 review | — | #76 | 2026-11-24 |
| B-046 | done | Minor ревью #66: зафиксировать harness-изменение (проверка модели сессии) в `CHANGELOG` → `Unreleased → Changed`; уточнить поведение subagent'а с собственной не-Flash моделью без явной `model:` | PR #66 review | Полнота CHANGELOG и определённость правила | #69 | 2026-11-23 |
| B-047 | done | Document cache hardening: `load()` ловит `ValidationError`/`ValueError`/`TypeError`/`ArithmeticError`; экранировать ключ `__eggpipe_type__` в пользовательских словарях; `_closure_matches` использует мемоизированный digest; тесты: `exc.code`, `--entity` → `len(calls) == 2`, тип `constraints.max` | PR #74/#75 review | Повреждённый кэш не роняет прогон | #79 | 2026-11-24 |
| B-036 | done | `troubleshooting.md`: подсказка про `gen list --all`; уточнить формулировку CHANGELOG (подсказка только при полной неудаче загрузки) | PR #52 review | DX при сломанных плагинах | #81 | 2026-11-24 |
| B-037 | done | Изоляция тестов: общий хелпер `tests/helpers.py::patch_entry_points` с фильтрацией по группе вместо инлайновых `fake_entry_points` (`tests/test_cli.py`, `tests/test_plugin_loader.py`); reference-примеры фильтруют `issues` по id примера; cookbook — установка примера до тестов (включает B-038) | PR #52/#53 review | Тесты не изолируют чужие группы; хрупкость в общем окружении | #81 | 2026-11-24 |
| B-050 | done | ТЗ v2.5: метрики hits/misses кэша; публикация формата `.eggpipe/cache/`; `eggpipe_version` в примере manifest; пакет с roadmap 0.5.0 п. 3 | PR #46/#47/#73 review | Единый пакет изменений ТЗ | #82, #84 | 2026-11-24 |
| B-042 | dropped | dropped: включено в B-025 | PR #49 review | — | #87 | 2026-11-25 |
| B-049 | dropped | dropped: включено в B-048 | PR #72/#74/#78, #82/#84 review | — | #87 | 2026-11-25 |
| B-052 | dropped | dropped: включено в B-025 | PR #82/#84 review | — | #87 | 2026-11-25 |
| B-051 | done | Document cache hardening, раунд 2: `_meta_state()` ловит `RecursionError` и тест на него; унифицировать наборы исключений в `remember()`/`_meta_state()`; усилить тесты: причина промаха в `test_deeply_nested_payload_is_miss`, `RecursionError` из `restore_document`, `entity("User") is not None`; после rename карта `paths` хранит устаревшее отображение; тест «L1-хит → `persist()` не вызывается» | PR #79, #84 review | Битый `meta.json` не роняет прогон, единое правило для недоверенного кэша | #91 | 2026-11-25 |
| B-053 | done | Harness: сузить `edit`/`read` pr-reviewer до `/tmp/opencode/pr-*.md`; DOC146 проверять итоговый эффект с учётом поздних `allow`; уточнить формулировки «Не проверено» и случай непереданных критериев | PR #83/#85 review | Точные права и однозначный вердикт | #94 | 2026-11-25 |
| B-054 | done | Logging: абсолютные пути в debug-сообщениях при JSON-режиме; `_escape` для `\n`/`\r`; привязать `run_id`/`event`/`duration_ms` к логам движка; policy-тест «без секретов и абсолютных путей» | PR #84 review | Инварианты structured logging | #93 | 2026-11-25 |
| B-055 | done | Benchmark follow-ups (#88 review): убрать лишний `_generate(...)` перед циклом в `_measure_noop`/`_measure_changed`; переименовать подпись заполненного `CacheReport` в `test_render_contains_rows` с `"no-op"` на `"changed"` | PR #88 review | Меньше лишних прогонов и яснее тест | #93 | 2026-11-25 |
| B-057 | done | Structured logging, пути и тесты: `display_path` — один `os.path.relpath` от resolved путей (симлинки без длинной `../`); `relative_text` — POSIX, все вхождения базы, root-base; `DocumentCache._display_path` через общий helper; fallback-запись экранирует все control-символы; тесты POSIX/симлинк/control/повтор базы, E2E CLI `EGGPIPE_LOG_MODE=json`, многострочный pydantic `_summary`; `plugins.md` — требование к тексту `DocumentError` | PR #93 review | Единый безопасный рендер путей | #96 | 2026-11-25 |
| B-040 | done | ADR-0022: политика версий в документации (`DOC161`, allowlist, `bump_version.py`, `mike` из `pyproject.toml`), ссылка из release guide | PR #51 review | Зафиксированное решение | #98 | 2026-11-25 |
