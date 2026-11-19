# Backlog

Конкретные отложенные задачи. Roadmap задаёт направления и вехи, здесь — мелкие
улучшения, технический долг и follow-up после ревью.

## Правила

- Каждый отложенный minor получает ID `B-NNN`.
- Одна таблица: закрытие меняет «Статус», строки не переносятся между секциями.
- Запись содержит источник, суть и импакт.
- Статусы: `open`, `done`, `dropped`; при закрытии заполняются PR/дата, для `dropped`
  причина пишется в «Задача» с префиксом `dropped:`.
- Если задача вырастает до отдельной вехи, она переносится в `roadmap.md`, а здесь
  остаётся ссылка.
- Ревьюер только сообщает находки; автор PR фиксирует minor в `Backlog candidates` PR body,
  а в этот файл он попадает на Backlog closeout.
- Перед новой фичей backlog groomится: закрыть или явно отложить записи; держать
  не больше 10 открытых.

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
| B-025 | open | Закрыть P2 из audit 2026-11-18 (v2.1 refs, ADR legacy, терминология, format API); `docs/user/plugins.md` в `LLMS_FULL_SOURCES` и freshness-проверка `docs/ai`; уточнить в отчёте аудита, что P2 закрываются после 0.4.0 | audit report, PR #43/#46 review | Документация без stale-оговорок | — | — |
| B-026 | done | CLI info: `format list` показывает `api_version`/`extends`/`base_versions`; убрать dead `getattr(plugin, "base_versions", {})`; в `cli.md` указать, что did-you-mean работает для `gen info` и `format info`; покрыть тестами пустой список доступных и отсутствие близких совпадений | PR #41 review | Полная картина плагинов, точные docs и тесты | #49 | 2026-11-19 |
| B-027 | done | Plugin discovery DX: подсказка `gen list --all` при пустом списке; общий тестовый хелпер фильтрует entry points по группе (инлайновые моки — B-037) | PR #41 review | Путаница при сломанных плагинах | #52 | 2026-11-19 |
| B-028 | dropped | dropped: `gen info --plugin PATH` перенесён в roadmap 0.6.0 — требует новой версии ТЗ | PR #41 review | Отладка плагина до установки | #48 | 2026-11-19 |
| B-029 | done | Reference-примеры: `test_contract.py` читает `plugin.output_scope` напрямую и падает на eggpipe 0.3.2 из PyPI — перейти на `getattr` или поднять зависимость; путь в `pyrightconfig.json`; ссылка в корневом `README.md`; формулировка snake_case/PascalCase в cookbook; пустая сущность в SQL; тесты discovery, generic id и `config.options` | PR #42 review | Совместимость, docs и покрытие примеров | #53 | 2026-11-19 |
| B-030 | dropped | dropped: включено в B-029 | PR #42 review | — | #48 | 2026-11-19 |
| B-031 | open | Contract errors: код для ошибок времени декорирования; вынести `_describe_generator_location` в общий внутренний модуль; hint-литералы — в константы | PR #43 review | Непоследовательный вывод, дублирование | — | — |
| B-032 | dropped | dropped: включено в B-025 | PR #43 review | — | #48 | 2026-11-19 |
| B-033 | dropped | dropped: включено в B-026 | PR #41 review | — | #48 | 2026-11-19 |
| B-034 | done | Пост-релизные правки docs: дубль `create_pr.py` в CHANGELOG и порядок секций; версия в примерах `system-design` §8/§12; stale «0.3.2» в шапке `session-log.md`; раздел аудита в roadmap §5; состав 0.5.0 без benchmarks; пример `major.minor` в `release.md` | PR #45–#47 review | Читаемость заметок, доверие к примерам | #50 | 2026-11-19 |
| B-035 | open | `bump_version.py`: покрыть тестами `main()`/`--dry-run` и ветки ошибок; включить скрипт и его тест в `REQUIRED_FILES` | PR #51 review | Регрессии релизного скрипта | — | — |
| B-036 | open | `troubleshooting.md`: подсказка про `gen list --all`; уточнить формулировку CHANGELOG (подсказка только при полной неудаче загрузки) | PR #52 review | DX при сломанных плагинах | — | — |
| B-037 | open | Инлайновые `fake_entry_points` в `tests/test_cli.py` (8 мест) не фильтруют группу — перевести на общий хелпер | PR #52 review | Тесты не изолируют чужие группы | — | — |
| B-038 | open | Reference-примеры: фильтровать `issues` по id примера (общий venv); cookbook — «перед запуском установите пример» | PR #53 review | Хрупкость теста в общем окружении | — | — |
| B-039 | open | `release.md`: иллюстрация `major.minor` (`1.2`) и примеры путей `/0.3/`, `/0.4/` рассогласованы; `DOC161` называть «проверкой», а не «правилом» | PR #51 review | Единообразие документации | — | — |
| B-040 | open | Оформить ADR о политике версий в документации (`DOC161`, allowlist, `bump_version.py`); критерий — правило действует шире релиза | PR #51 review | Зафиксировать решение | — | — |
| B-041 | open | Пример manifest в ТЗ v2.4 показывает `eggpipe_version: "0.1.0"` (актуальная версия не отражена); уточнение по отчёту аудита — в B-025 | PR #46/#47 review | Stale пример в актуальном ТЗ | — | — |
| B-042 | open | `engineering/decisions/eggpipe.md`: макет `format list` расходится с реальным выводом | PR #49 review | Документ идей вводит в заблуждение | — | — |
