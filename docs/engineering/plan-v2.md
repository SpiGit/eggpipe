# План Eggpipe v2.0

- **Дата:** 2026-11-12
- **Основание:** [ТЗ v2.0](requirements/v2.0.md), [ревью v2.0](reviews/2026-11-12-v2-review.md)
- **Статус:** E0–E8 выполнены; следующий этап — E9

---

## 1. Цель

Привести реализацию к ТЗ v2.0:

- Eggpipe как единая идентичность: package, CLI, config, state;
- форматы с независимыми версиями, наследованием и схемами;
- model units, слои и раскладки источников;
- decorator API генераторов;
- глобальный manifest и ownership;
- CLI/UX, diagnostics и JSON v2.

## 2. Не-цели

- Обратная совместимость с `metadata-generator`/`mg`/`.mg.yaml`/`.mg/`.
- Публикация в PyPI до завершения переименования и стабилизации.
- Новые генераторы, кроме TPC-H примера.
- GUI/Web.

## 3. Принципы

- Исторические ТЗ v1.0–v1.4 не редактируются.
- Все изменения — через ТЗ v2.0 и ADR.
- Код и документация синхронизируются в одном эпике.
- После каждого эпика: `docs-check`, ruff, pyrefly, pytest, build.
- Диагностические коды не переиспользуются.

---

## 4. Эпики

### E0. Базовая линия документации

**Статус:** E0–E1 выполнены.

- [x] ТЗ v2.0.
- [x] v1.4 → история.
- [x] Eggpipe docs, CLI/config target.
- [x] Ревью v2.0.
- [x] Закоммитить docs v2.0.
- [x] Добавить `docs/engineering/reviews/2026-11-12-v2-review.md` в навигацию/индекс.

**Критерий:** `check_docs --strict` и `mkdocs --strict` зелёные.

### E1. Переименование package/CLI/config/state

**Зависимости:** E0.

Задачи:

- [x] `pyproject.toml`: `name = "eggpipe"`, script `eggpipe = "eggpipe.cli.main:app"`.
- [x] `src/metadata_generator` → `src/eggpipe`.
- [x] Все импорты `metadata_generator` → `eggpipe` в src/tests/tools/examples.
- [x] Entry points: `eggpipe.generators`, `eggpipe.formats`.
- [x] Config loader: `.mg.yaml` → `.eggpipe.yaml`; config discovery.
- [x] State: `.mg/` → `.eggpipe/`; manifest/lock paths.
- [x] Env prefix `MG_*` → `EGGPIPE_*`.
- [x] Example package: dependency `eggpipe`, entry points `eggpipe.*`.
- [x] `uv.lock`, editable installs, `.venv`.
- [x] CLI help/usage strings.
- [x] TPC-H configs: `.mg.yaml`/`.mg.split.yaml` → `.eggpipe.yaml`/`.eggpipe.split.yaml`.

**Критерий:** `eggpipe --help`, `pytest`, `uv build`, `check_wheel` зелёные; старые имена остаются только в истории/ADR.

### E2. Core-модели и публичный API

**Зависимости:** E1.

Задачи:

- [x] `FormatInfo`, `FormatSchema`, `MergePolicy`, `EntityIdentity`, `FieldIdentity`.
- [x] `Entity.format`, `format_version`, `layer_sources`, `FieldDef.source`.
- [x] `GenerationContext.formats: frozenset[FormatInfo]`; удалить `format`/`format_version`.
- [x] `ModelSlice`/`SourceModel` helpers для форматов.
- [x] Обновить `__init__.__all__` и `py.typed`.

**Критерий:** контрактные тесты публичного API; mypy/pyrefly/pyright.

### E3. Форматы: наследование и версии

**Зависимости:** E2.

Задачи:

- [x] `FormatPlugin`: `extends`, `base_versions`, `supported_versions`, `schemas`.
- [x] `EntityModelFormat`: `schemas` по версиям, `layer_entity`/`full_entity`.
- [x] Registry: цепочка `extends`, цикл/глубина, проверка `base_versions`.
- [x] `version` опционален: latest.
- [x] Проверка `full_entity` — подкласс базовой; `primitive_types` — надмножество.
- [x] Ошибки MG008/MG034.

**Критерий:** тесты наследования, версий, схем, latest, циклов.

### E4. Model units, слои и источники

**Зависимости:** E3.

Задачи:

- [x] `layout`: `monolith`, `file-per-model`, `directory-per-model`; обязателен.
- [x] `model_dirs`, `files`, `models` override; glob.
- [x] `resources`: top-level + `models.<dir>.resources`; alias/glob/границы.
- [x] Discovery: `.eggpipe`, output dirs, hidden, symlink.
- [x] Model unit: одна сущность; layer chain; full/delta validation.
- [x] Layer merge: KEYED/APPEND/UNION/ERROR; provenance.
- [x] Empty dirs/empty delta/glob warnings; MG027/MG035–MG038.

**Критерий:** тесты layout/discovery/resources/merge; TPC-H в directory-per-model.

### E5. Generator API: decorator и compatibility

**Зависимости:** E2, E3.

Задачи:

- [x] `@generator` decorator: metadata, validation, registration.
- [x] Инъекция `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
- [x] Нормализация return types.
- [x] `input_formats` обязателен; MG301/MG302.
- [x] Pre-flight проверка форматов; MG033 exit 2.
- [x] Plugin loader: decorator objects, entry points.
- [x] `gen list/info` с `input_formats`.

**Критерий:** contract-тесты, decorator/class API, mixed formats.

### E6. Глобальный manifest, ownership, cleanup

**Зависимости:** E1, E4.

Задачи:

- [x] `.eggpipe/manifest.json`; `manifest_version: 2`; `eggpipe_version`.
- [x] Locations `(generator, output_dir)`; `formats`.
- [x] Ownership/--force: только unowned; no steal.
- [x] Cross-generator exact/casefold/prefix conflicts MG042.
- [x] `eggpipe clean`: global manifest, no config/plugins; `--root`.
- [x] Stale locations MG051; corrupted/unsupported MG052.
- [x] Global lock `.eggpipe/lock`.

**Критерий:** tests ownership/cleanup/concurrency/mixed formats.

### E7. CLI/UX, diagnostics, JSON v2

**Зависимости:** E1, E5, E6.

Задачи:

- [x] Commands/flags из v2.0 §8.
- [x] Config discovery; `init --layout`.
- [x] `config schema`, `model schema --format`, `gen info`, `format info`.
- [x] Exit codes 0/1/2/130.
- [x] `diagnostics.ignore` только warnings.
- [x] JSON report v2 (`report_version: 2`).
- [x] Text formatter: warnings/errors to stderr.

**Критерий:** CLI integration tests, JSON schema/golden, exit codes.

### E8. TPC-H example и golden

**Зависимости:** E4, E5, E6, E7.

Задачи:

- [x] Переименовать configs/package entry points.
- [x] Перевести на `layout`/`files`/`resources`.
- [x] Использовать decorator API.
- [x] Проверить single/split/postgres-model.
- [x] Обновить golden и README.

**Критерий:** golden tests, реальный `eggpipe generate`.

### E9. Качество, CI, релиз

**Зависимости:** E1–E8.

Задачи:

- [ ] Полный pytest/coverage.
- [ ] ruff/pyrefly/basedpyright.
- [ ] docs-check/mkdocs.
- [ ] `uv build`/`check_wheel`.
- [ ] CI: example install, config names.
- [ ] Release docs: PyPI name `eggpipe`, trusted publisher, repo name.
- [ ] Версия пакета: 0.2.0 или 0.3.0 (решить).

**Критерий:** все проверки зелёные; release workflow готов.

### E10. P2-документация

**Зависимости:** E0.

- [ ] ADR-0007–0010: пометка «историческая ссылка на v1.4».
- [ ] System Design pyproject fragment.
- [ ] `--plugin` статус.
- [ ] `gen list --all`, `--show-secrets` в таблице флагов.
- [ ] Alias collision MG025/MG032.
- [ ] Harness old names.
- [ ] README stage.
- [ ] Session context tree/ADR-0010.

---

## 5. Порядок

1. E0 — docs v2.0 commit.
2. E1 — package/CLI/config rename.
3. E2 — core models/API.
4. E3 — formats.
5. E4 — sources/layers.
6. E5 — decorator API.
7. E6 — manifest/ownership.
8. E7 — CLI/UX/diagnostics/JSON.
9. E8 — TPC-H.
10. E9 — quality/release.
11. E10 — P2 docs (можно параллельно).

## 6. Риски

| Риск | Митигация |
|------|-----------|
| Большой diff переименования | отдельный эпик E1, автоматические замены, тесты после |
| Docs target ≠ code до E1 | явная пометка в session context, E1 первым |
| Сложность layer merge | property/contract-тесты, ADR-0008 |
| Mixed formats | pre-flight MG033, тесты |
| Manifest без совместимости | удалить `.mg`, тесты v2 |
| TPC-H golden | обновлять только после стабилизации шаблонов |
| PyPI/CI renaming | release docs, trusted publisher |

## 7. Definition of Done

- [ ] ТЗ v2.0, System Design, README, AGENTS, session context согласованы.
- [ ] Старые имена только в истории/migration.
- [ ] `check_docs --strict`, `mkdocs --strict`.
- [ ] `ruff`, `pyrefly`, `basedpyright`, `pytest --cov`.
- [ ] `uv build`, `check_wheel`.
- [ ] `eggpipe` install/run.
- [ ] TPC-H golden.
- [ ] Release checklist обновлён.
