# Ревью проекта Eggpipe — 2026-11-13

- **Модель ревью:** Qwen3.8 Max (`opencode-go/qwen3.8-max`) — оба суб-агента (spec-reviewer для документации и general для кода) выполнены на этой же модели.
- **Формат:** два независимых read-only ревью — ТЗ/документация и код; ни один файл не изменялся (кроме создания настоящего отчёта).
- **Состояние working tree:** включает незакоммиченный рефакторинг `discovery.py`, `artifact_writer.py`, `plugin_loader.py` (сессия «patterns review»); тесты проходят и на нём.

## Сводка

| Область | Итог | P0 | P1 | P2 |
|---------|------|----|----|----|
| Документация (ТЗ v2.0, ADR, SD, harness) | Есть блокеры согласованности | 2 | 11 | 15 |
| Код (src/eggpipe, ~6200 строк, 201 тест) | Релиз-кандидат по качеству | 0 | 3 | 16 |

Общий вывод: семантическое ядро (null-матрица, композиция, ownership/manifest, `input_formats`/MG033, exit codes) согласовано между ТЗ, ADR и кодом и корректно реализовано. Основные проблемы — расхождения машиночитаемых контрактов (JSON-отчёт v2: `action` vs `status`, `timings`), дерево модулей ТЗ/SD/код, устаревший skill `plugin-contract` и опечатка `GeneratorContext` в нормативных примерах. Рекомендуется ТЗ v2.1 + ADR-0011 (см. ниже).

---

## Часть 1. Ревью документации (ТЗ)

### P0 — противоречие контракту / потеря смысла

#### P0-1. `GeneratorContext` — несуществующее имя публичного API в примерах

- `docs/requirements/v2.0.md:785` (§6.1.1, пример decorator API), `README.md:66`, `docs/plugin-guide.md:13`:
  `from eggpipe import (..., GeneratorContext, ...)`.
- В списке публичного API (ТЗ §6.2, `v2.0.md:835`; SD §2, `index.md:85`) имя — `GenerationContext`; `GeneratorContext` не существует. В тех же примерах аннотация — `context: GenerationContext` (v2.0.md:798). Копирование примера README даёт `ImportError`.
- Исторический `v1.4.md:770` содержит ту же опечатку — **не трогать** (read-only).
- **Действие:** исправить в README.md:66 и plugin-guide.md:13; в ТЗ v2.0 — редакторская опечатка, допустима точечная правка либо включение в v2.1.

#### P0-2. Skill `plugin-contract` противоречит актуальному контракту v2.0

`.opencode/skills/plugin-contract/SKILL.md`:
- строки 13, 27: старое имя пакета `metadata_generator` (переименование завершено, plan-v2 E1 `[x]`);
- строки 15–18: список API урезан (нет `FormatInfo`, `FormatSchema`, `EntityIdentity`, `FieldIdentity`, `MergePolicy`, `generator`, `Provenance`, `git_provenance`, `UNSET`, `PRIMITIVE_TYPES`, `Constraints`, `FormatPlugin`, `EntityModelFormat`); строка 74 при этом утверждает, что `EntityModelFormat` входит в API — самопротиворечие;
- строки 35–43: пример `MyGenerator` **без обязательного `input_formats`** — противоречие ТЗ §3.4.3/§6.1 (`v2.0.md:296–297, 749`, MG301) и чек-листу самого skill'а (строка 101).
- **Действие:** переписать разделы «Публичный API» и пример по ТЗ v2.0 §6.1–6.3 и SD §2. Формально покрыто E10, но по факту это P0.

### P1 — существенная несогласованность

| # | Место | Суть | Действие |
|---|-------|------|----------|
| P1-3 | ТЗ §8.7 (`v2.0.md:1017–1024`), §10.6 (:1247); SD §7.4 (:1138), §8.2 (:1211); `eggpipe.md:381`; код `report.py:26` | JSON-отчёт v2: документы требуют поле `action` (`create/update/skip/delete/conflict`), код — `status` (`create/update/skip/error/drift`). ТЗ не перечисляет допустимые значения `action` (пример ≠ спецификация); `error`/`drift` в ТЗ не определены; `generators[].status` не перечислен | ТЗ v2.1: зафиксировать имя поля и полный enum для `artifacts[]` и `generators[].status`; синхронизовать SD §7.4, eggpipe.md, код |
| P1-4 | ТЗ §8.7 (`v2.0.md:1032–1039`); SD §7.4 (:1147–1154); код `engine.py:463` | `timings`: ТЗ требует 6 полей (`discovery_ms`…`total_ms`), код заполняет только `total_ms` | Реализовать замер фаз либо в v2.1 объявить обязательным только `total_ms` с обоснованием |
| P1-5 | ТЗ §9.1 (:1100), §9.4 (:1137); SD §4.4 (:766); `diagnostics.md:24`; код `engine.py:488–511` | MG014: ТЗ — «только file-per-model, opt-in»; SD — устаревший термин «file-per-entity»; diagnostics.md потерял ограничение; код применяет ко всем документам | Решить: код к ТЗ либо v2.1 переопределяет область (тогда указать mtime какого файла для monolith/directory-per-model); независимо — исправить SD:766 и diagnostics.md:24 |
| P1-6 | ТЗ §11.1 (:1258–1308); SD §10 (:1353–1452); факт `src/eggpipe/**` | Дерево модулей расходится втрое: ТЗ — `cli/generate.py`/`cli/watch.py`, нет `core/discovery|layers|slicing|provenance`; SD — `cli/main.py` (как в коде), но заявлены несуществующие `engine/planning.py`, `engine/locking.py`, `watch/cache.py`; `examples/` в SD не совпадает с фактом | v2.1: привести §11.1 к факту/цели (или отсылка на SD как единственный источник); SD §10 обновить, future-модули помечать явно |
| P1-7 | ТЗ §11.6 (:1423), §13 (:1467), §14 (:1499); SD §6.3 (:1014); README:130; plugin-guide; код `cli/main.py:276,390` | `--plugin`: «Future» в ТЗ/SD, но реализован и описан как работающий; внутри ТЗ несогласовано (§13 включает в поставленный v0.3); отсутствует в таблице флагов §8.2 | v2.1: зафиксировать как поставленный dev-only флаг + добавить в §8.2; SD — снять «Future» |
| P1-8 | `README.md:83–84` | Пример entry point `my-project-generators = "...:MyProjectGenerator"` нарушает контракт «id == entry point» (ТЗ :747, SD :984 — Error) и форму decorator API (цель обязана быть декорированной функцией, ADR-0010) | `my-project-generator = "my_project.plugins:my_project_generator"` |
| P1-9 | `eggpipe.md:305–307`; код `cli/main.py:582–584`; README:123 | `model schema` без `--format`: eggpipe.md — «ошибка», код — печатает схему `ModelDocument`; ТЗ §8.1 (:917) не фиксирует | v2.1: зафиксировать фактическое поведение; eggpipe.md исправить |
| P1-10 | `docs/reference/diagnostics.md` строки 6, 8, 11, 54 | Статусы «v0.4» у уже реализованных MG027–MG038/MG301/MG302/MG050–052; MG001 «зарезервирован» противоречит ТЗ §9.1 (:1060, активная Error) и SD:753, при этом ТЗ §3.3 (:226) даёт «MG001/MG004» неоднозначно; у MG042 нет prefix-конфликта (ТЗ §9.2 :1112) | Обновить статусы и MG042; для MG001/MG004 — v2.1 разводит смыслы или закрепляет «зарезервирован» |
| P1-11 | ТЗ §6.2 (:835); ADR-0005 §2; ADR index | Решения v2.0 без ADR: `Provenance`/`git_provenance` в стабильном API (ADR-0005 не уточнён); переименование mg→eggpipe (breaking) зафиксировано только в ТЗ/eggpipe.md, косвенно затрагивает ADR-0009 | Новый **ADR-0011** «Публичный API v2.0 и идентичность Eggpipe»; в adr/index.md пометки «уточнено ADR-0011»; старые ADR не переписывать |
| P1-12 | `.session-context.md:27,29` | Выдаёт снятые требования v1.2 за актуальные: «один запуск — один формат», per-generator manifest (отменён ADR-0009) — противоречит строкам 308–310, 341 того же файла | Переписать раздел как историческую сводку или заменить актуальными решениями |
| P1-13 | `README.md:194–195`; `AGENTS.md`; `CHANGELOG.md:14` | Устаревшие статусы: «далее — переименование» (выполнено), «ядро v0.1–v0.3» (реализован v0.4-объём), «переименование — отдельный этап» | Синхронизировать статусы (требование DoD AGENTS.md) |

### P2 — терминология, ссылки, стиль

| # | Место | Суть |
|---|-------|------|
| P2-14 | `v2.0.md:1126–1127` | MG018 учтён дважды (явно + внутри диапазона MG010–MG021) |
| P2-15 | `diagnostics.md:3–4` vs `v2.0.md:1123–1130` | Заголовки диапазонов расходятся; MG030/MG033 численно 0xx, но отнесены к MG3xx — оговорить, что области семантические |
| P2-16 | `v2.0.md:1466`; SD:766 | Термины v1.0 `file-per-entity`/`directory-per-entity` вместо `file-per-model`/`directory-per-model` |
| P2-17 | `v2.0.md:641,1686`; SD:519; `v2.0.md:1682` | `model_dirs: "*"` (строка) при типе `tuple[str, ...]`; пример §15.5 без обязательного `version` |
| P2-18 | `v2.0.md:926,977,920` | Флаги `--root`, `--debounce-ms`, `--all` отсутствуют в таблице §8.2 и сигнатурах SD |
| P2-19 | `v2.0.md:704` | «Срез без closure-ссылок недопустим» — неоднозначно; переформулировать как гарантию closure + MG018 |
| P2-20 | `v2.0.md:401–402` vs :1079 | Discovery «YAML не-документ не подхватывается» vs MG023 Error — уточнить границу |
| P2-21 | `v2.0.md:978` vs SD:1334 | Watch Ctrl+C: «exit 0/130» vs «0; по сигналу — 130» — унифицировать |
| P2-22 | `v2.0.md:297,815`; SD:548 | Плейсхолдеры «MG3xx» в нормативном тексте; для абсолютного `output_dir` код не назначен |
| P2-23 | ADR-0008:87 | Английское предложение в русском документе; ADR задним числом не переписываются — оставить или корректура с пометкой |
| P2-24 | `eggpipe.md:470` | Открытый вопрос о переименовании пакета — выполнен, закрыть |
| P2-25 | SD §12 (:1509–1552) | pyproject-фрагмент устарел (нет `typing-extensions`, extra `jinja`, расширенный dev, hatch-targets) |
| P2-26 | SD:1025,1027 | Комментарии «(P2)» у реализованного `model schema`; `format list` без `info` |
| P2-27 | README:140, release.md:13, CONTRIBUTING:32 vs AGENTS.md | `ruff format --check` с `examples` / без — унифицировать |
| P2-28 | `.session-context.md:140–293,383–392` | Дерево файлов и «Следующие шаги» устарели (выполненные E2–E8) |

### Результат `check_docs --strict`

Суб-агент `spec-reviewer` работает без shell (deny в `.opencode/agents/spec-reviewer.md`), поэтому выполнена **ручная репликация всех проверок** `tools/check_docs.py` (DOC100–DOC160): обязательные файлы, реестр версий (ровно одна «Актуальная»), ссылки на v2.0, deny-правила opencode.json для v1.0–v1.4, frontmatter harness, относительные ссылки, запрещённые термины, множество кодов MGxxx — **все проверки OK, ожидаемый результат 0 ошибок / 0 предупреждений**.

Важно: скрипт **не ловит** ни одну из находок P0/P1 выше — зелёный `check_docs` не означает согласованности по существу.

### Сильные стороны документации

1. Семантическое ядро согласовано дословно: null-матрица (ТЗ §3.6 = ADR-0003 = SD §3.1), MG033/exit 2, ownership/manifest/cleanup (ТЗ §10 = SD §8 = ADR-0004+0009), MergePolicy (ТЗ §3.5.5 = ADR-0008 = SD §4.5).
2. Список публичного API идентичен в ТЗ §6.2 и SD §2.
3. Явная матрица версионируемости контрактов (§11.5.3): `report_version`, `manifest_version`, `api_version`.
4. Дисциплина истории: одна актуальная версия, deny-защита v1.0–v1.4, ADR не переписаны, пометки «уточнено ADR-000x».
5. Автоматизация: `check_docs.py` + docs-CI; прозрачный процесс (`docs/reviews/`, `plan-v2.md` E10 уже трекают часть P2).

---

## Часть 2. Ревью кода

### Итоги проверок

| Проверка | Результат |
|----------|-----------|
| `ruff check .` | 0 нарушений |
| `ruff format --check src tests tools examples` | 73 файла отформатированы, OK |
| `pyrefly check` | 0 ошибок (13 suppressed) |
| `pytest -q` | **201 passed, 0 failed, 2.93 s** |

Примечание: `uv` в PATH окружения суб-агента отсутствовал, проверки выполнены идентичными инструментами из закоммиченного `.venv`.

Старых имён `mg` / `metadata_generator` / `.mg.yaml` / `.mg/` в `src/`, `tests/`, `tools/`, `examples/`, `pyproject.toml` **нет**; коды `MGxxx` сохранены намеренно (стабильны по ТЗ), набор кодов в src совпадает с `docs/reference/diagnostics.md` 1:1.

### P1

| # | Файл, строки | Суть | Рекомендация |
|---|--------------|------|--------------|
| K1 | `engine/report.py:23–29` | JSON-отчёт v2: в коде поле `status` (+ значения `error`/`drift`), ТЗ §8 и SD §7.4 требуют `action`. Публичный контракт отчёта (см. док. P1-3) | Привести к ТЗ либо зафиксировать отклонение в v2.1/ADR |
| K2 | `engine/engine.py:463` | `timings` содержит только `total_ms` вместо 6 полей ТЗ (см. док. P1-4) | Добавить замер фаз в `build()`/`_write_pending()` |
| K3 | `engine/artifact_writer.py:297–298` | `write()` делает ранний `return []` при пустом `plan.artifacts`: manifest не обновляется, cleanup location не выполняется. Если генератор выдал 0 файлов, артефакты прошлого запуска останутся на диске и в manifest даже при `cleanup: enabled` (ТЗ §10.5) | Убрать ранний выход: прогонять `_cleanup_location` с `current_paths=set()` и удалять опустевший location |

### P2

| # | Файл, строки | Суть | Рекомендация |
|---|--------------|------|--------------|
| K4 | `artifact_writer.py:422–435` | Stale lock: PID записывается, но не используется; после SIGKILL все запуски (включая watch) падают с MG300 до ручного удаления; текст ошибки не подсказывает решение | Проверять живость PID или добавить подсказку про stale lock |
| K5 | `artifact_writer.py:406–413`, `engine.py:427–434` | Двойной код в сообщении: «error: MG052: MG052: …» | Убрать префикс кода из текста исключения |
| K6 | `engine.py:151–152, 488–511` | MG014 применяется ко всем документам; ТЗ §9.4 — только file-per-model (см. док. P1-5) | Фильтровать по layout |
| K7 | `cli/main.py:546–556` | `model validate` создаёт `Parser()` со встроенным реестром — документ плагинного формата получит MG007 | Использовать `_load_format_registry()` |
| K8 | `artifact_writer.py:300–344` | ТЗ §10.4: staging-каталоги «удаляются при старте и по сигналу» — реализован только `finally` | Sweep `.eggpipe-staging-*` при старте записи |
| K9 | `engine.py`, `artifact_writer.py` | `--plan` не показывает `delete` и `conflict` (ТЗ §10.6) | Включать delete/conflict в план/отчёт |
| K10 | `core/parser.py:11`; `core/discovery` ↔ `config` | Инверсия слоёв: `core` → `engine` (`FormatRegistry`); пакетный цикл `core ↔ config` | Protocol-приём как в `layers.py` (`FormatLookup`); вынести общие config-типы |
| K11 | `utils/exceptions.py:56` | `class LookupError(EggpipeError)` затеняет builtin и не используется | Удалить |
| K12 | `watch/watcher.py:32–49` | Debouncer не предотвращает перекрывающиеся запуски → параллельный `generate()` → LockError/MG300 в логах watch | Флаг «запуск активен» + отложенный повторный trigger |
| K13 | `artifact_writer.py:596–603` | `_write_json_atomic` без fsync файла/каталога; фиксированное имя `manifest.json.tmp` (гонка для публичного `save_manifest()` вне lock) | Добавить fsync; документировать требование lock |
| K14 | `artifact_writer.py:565–589` | Drive-relative `C:foo` (Windows) не отсеивается — ТЗ §9.2 «без drive-letter» | Проверка `^[A-Za-z]:` в первом сегменте |
| K15 | `interfaces/generator.py:32–41` | `GenerationContext` frozen, но `variables`/`imports`/`sources` — изменяемые контейнеры | MappingProxy/копии |
| K16 | `core/provenance.py:22–36` | `subprocess.run` без timeout — теоретический hang | `timeout=` + подавление `TimeoutExpired` |
| K17 | `engine.py:493` | `document.path.stat()` без защиты — `OSError`, если файл исчез между discovery и валидацией | try/except с диагностикой |
| K18 | `engine.py:484–485`, `parser.py:53` | Магический default `"1"` в `_plugin_version`; «latest» = `supported_versions[-1]` предполагает сортировку | Константа + требование сортировки в контракте FormatPlugin |
| K19 | Структура vs ТЗ §11.1 | См. док. P1-6 — расхождение дерева модулей | Решение за мейнтейнером (ТЗ или код) |

Проверено и **не подтвердилось**: гонка plan→write (всё под lock), symlink/traversal (resolve + is_relative_to, есть тест), case-коллизии (casefold), детерминизм (сортировки везде), кодировки (UTF-8, LF, без BOM, NFC), `--plan`/`--check` без побочных эффектов и без lock, `--force` не отбирает чужое, MG033 → exit 2 до записи.

### Оценка тестов (201)

Покрытие хорошее: security/writer (17: traversal, symlink, case-collision, CRLF/BOM, ownership, force, drift, lock, cleanup, manifest v1 rejected, corrupted), contract (13), determinism (1, byte-identical), golden TPC-H (1), property hypothesis (4), CLI (21: exit 2, JSON v2, strict/ignore, clean non-tty, local plugin, init), форматы/наследование (16).

Пробелы:
- нет мультипроцессного concurrency-теста (только held-lock в одном процессе);
- нет теста «генератор выдал 0 артефактов после непустого прогона» (K3);
- нет теста ключей `action`/`timings` JSON-отчёта против схемы ТЗ (поэтому K1–K2 не пойманы);
- watch — по одному unit/integration-тесту.

### Сильные стороны кода

- Иммутабельная доменная модель: pydantic `frozen=True`, `tuple`, sentinel `UNSET` с корректной сериализацией — null-матрица ADR-0003 реализована точно.
- Границы исключений плагинов: `validate_config()`/`generate()` → MG300, остальные генераторы продолжаются (ТЗ §8.4); `PluginIssue` без падения процесса.
- Строгий format registry: циклы, глубина ≤ 10, `base_versions`, `issubclass(full_entity)`, суперсет примитивов, резервирование `entity-model`.
- Безопасность записи: NFC, casefold/prefix-коллизии, Windows reserved names, symlink-escape, атомарный staging → `os.replace`, ownership pre-flight (MG042) — всё покрыто тестами.
- Детерминизм: сортировки на всех выходах; golden-тест.
- Дисциплина диагностик: структурированный `Diagnostic` с локацией, `DiagnosticPolicy` («ignore до strict»).
- Чистый стиль: focused-функции, dataclass-состояния (`_PlanState`, `_ResourceCollector`), `py.typed`, 0 ошибок строгого типизатора.
- CLI: единый `command_errors` для exit codes 1/2/130, redaction секретов, `--yes`/tty-гейт, JSON-lines для watch.

---

## Статус исправлений (follow-up)

Исправлено без новой версии ТЗ:

- **P0-1:** `GeneratorContext` → `GenerationContext` в README, plugin-guide и примере ТЗ.
- **P0-2:** skill `plugin-contract` переписан под публичный API v2.0.
- **P1-8:** entry point в README приведён к decorator API и `id`.
- **P1-10:** статусы `diagnostics.md` обновлены, MG042 дополнен prefix-конфликтом.
- **P1-12:** устаревшая сводка v1.2 в `.session-context.md` заменена актуальной.
- **P1-13:** статусы README/AGENTS/CHANGELOG синхронизированы с v2.0.
- **K3:** пустой план теперь выполняет cleanup предыдущего location.
- **K5:** двойной префикс `MG052: MG052:` убран.

Дополнительно выпущены ТЗ v2.1 и ADR-0011:

- ТЗ v2.1 фиксирует `action`/`status`, enum, `timings`, MG014, `--plugin`, `model schema`,
  MG001/MG004, дерево модулей, термины и флаги;
- ADR-0011 фиксирует публичный API v2.1 и идентичность Eggpipe;
- v2.0 переведена в историю и защищена `deny` в `opencode.json`.

Кодовые P1 тоже исправлены: `artifacts[].action`, все шесть `timings`, MG014 только для
`file-per-model`, `model validate` с plugin-реестром, удалён неиспользуемый `LookupError`.

Из кода P2 исправлены K4 (stale lock), K8 (sweep staging), K9 (`delete/conflict` в плане),
K12 (watch overlap), K13 (fsync + уникальный tmp), K14 (drive-relative), K15 (read-only
context containers), K16 (git timeout), K17 (stat OSError), K18 (plugin version default).
Остаётся K10 (слой core → engine / пакетный цикл с config) — архитектурный рефакторинг.

## Рекомендуемый план действий

1. **Сразу (без новой версии ТЗ):** P0-1 (`GeneratorContext` в README/plugin-guide), P0-2 (skill `plugin-contract`), P1-8 (README entry point), P1-12/P1-13 (статусы README/AGENTS/`.session-context.md`/CHANGELOG), P1-10 (diagnostics.md статусы), K3 (пустой план), K5 (двойной код).
2. **ТЗ v2.1 (новая версия по правилам AGENTS.md):** JSON-отчёт `action`/`status` + enum значений + `timings` (P1-3, P1-4, K1, K2), область MG014 (P1-5, K6), дерево модулей §11.1 (P1-6, K19), `--plugin` (P1-7), `model schema` без `--format` (P1-9), MG001/MG004 (P1-10), накопленные P2-14…P2-22.
3. **ADR-0011** «Публичный API v2.0 и идентичность Eggpipe» (P1-11).
4. **Код, бэклог P2:** K4 (stale lock), K6–K18 по приоритету; тесты на пустой план, ключи JSON-отчёта, мультипроцессный lock.
