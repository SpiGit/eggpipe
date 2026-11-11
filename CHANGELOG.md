# Changelog

Все заметные изменения проекта. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- Ядро v0.1, первый слой: `ModelDocument`/`SourceModel`/`ModelSlice`, `FieldDef`, `EnumDef`,
  `CustomType`, `UNSET`, YAML-парсер на `ruamel.yaml`, формат `entity-model`, семантический
  валидатор, срезы с замыканием по enums/types и naming-утилиты.
- Writer: ownership, per-generator manifest, atomic write, lock, `--plan`/`--check`.
- `Engine` (`build()`/`generate()`/`check()`), `GeneratorPlugin` и контракты генераторов.
- CLI `mg`: `generate`, `init`, `config show/validate`, `model validate`, `gen list/info`,
  `format list`, `clean` (placeholder до v0.2).
- Reference-плагин `examples/reference-generator` и golden-тест.
- v0.2: composition — `imports`, `entity.extends`, discovery каталогов, merge по ADR-0001,
  project-root boundary и `--allow-outside-imports`.
- Cleanup owned-артефактов (`off|prompt|enabled`), `--clean`, MG050.
- `sources[].input` и MG014 (`updated_at`).
- v0.3: format-плагины из entry points, `mg watch`, JSON-отчёт, provenance-утилита,
  `--plugin` для локальной разработки.
- Стабилизация: integration-тест watch, contract-тесты плагинов, security-тест symlink,
  руководство `docs/plugin-guide.md`.
- ADR-0003 (null-семантика/UNSET), ADR-0004 (ownership/cleanup), ADR-0005 (library API),
  ADR-0006 (format extension) и индекс ADR.
- `UNSET` больше не сериализуется как `default: null` — ключ опускается.
- `on_conflict: error` теперь даёт MG041 для любого существующего файла; `mg clean` берёт lock.
- Backlog P1/P2: `mg model schema`, `mg config schema`, единая точка logging,
  интерактивный `mg clean --yes`, устойчивый plugin loader с issues, флаги watch.
- Каталог диагностик `docs/reference/diagnostics.md`.
- ТЗ v1.2: модель `ModelDocument` → `SourceModel` → `ModelSlice`, контракты плагинов,
  ownership/manifest, CLI и диагностики.
- System Design v1.2 и ADR-0001 (семантика композиции).
- Agent harness: `AGENTS.md`, `opencode.json`, команды, skills и read-only `spec-reviewer`.
- Python-чекер документации `tools/check_docs.py` и docs-CI.
- Test harness: `pyproject.toml`, `uv.lock`, ruff, Pyrefly (strict), pytest, coverage.
- ADR-0002: Pyrefly вместо mypy.
- Delivery harness: сборка wheel/sdist, проверка артефактов и release-workflow.
- MIT License.

Ядро v0.1 и CLI `mg` ещё не реализованы.
