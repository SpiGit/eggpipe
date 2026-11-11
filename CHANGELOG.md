# Changelog

Все заметные изменения проекта. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### Added

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
