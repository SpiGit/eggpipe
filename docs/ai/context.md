# AI context

Компактный контекст для AI-агентов, работающих с Eggpipe.

## Идентичность

- Проект: **Eggpipe**.
- Package/import/CLI: `eggpipe`.
- Конфиг: `.eggpipe.yaml`; state: `.eggpipe/`.
- Актуальное ТЗ: `docs/engineering/requirements/v2.2.md`.
- Версия пакета: `0.3.0`; версия ТЗ: `2.2`.
- Статус: beta (0.x); до 1.0 breaking changes возможны (ADR-0014).

## Установка и проверки

```bash
uv sync --extra dev
uv run pytest --cov
uv run ruff check .
uv run ruff format --check src tests tools examples
uv run pyrefly check
uv run python tools/check_docs.py --strict
uv build
uv run python tools/check_wheel.py dist
```

## Публичный API

```text
GeneratorPlugin, GeneratorInput, GenerationResult, Artifact, GenerationContext,
FormatInfo, FormatSchema, ImportedFile, SourceModel, ModelSlice, Entity,
EntityIdentity, FieldIdentity, FieldDef, EnumDef, CustomType, GeneratorConfig,
NamingStyle, transform, Diagnostic, EngineReport, Engine, AppConfig,
ProjectConfig, ProjectConfigLoader, FormatRegistry, FormatPlugin,
EntityModelFormat, MergePolicy, generator, Provenance, git_provenance,
UNSET, PRIMITIVE_TYPES, Constraints
```

Всё из `core.*` и `engine.*` — внутреннее.

## Команды CLI

```text
eggpipe generate [MODELS] [-g ID] [--plan|--check] [--output-format json]
eggpipe watch [MODELS] [-g ID] [--debounce-ms N]
eggpipe init [PATH] --layout monolith|file-per-model|directory-per-model
eggpipe config show|validate|schema
eggpipe model validate|schema [--format NAME] [--version V]
eggpipe gen list [--all]|info
eggpipe format list|info
eggpipe clean [--dry-run] [--yes] [--root PATH]
```

## Документация

- Пользователям: `docs/user/`.
- AI: `docs/ai/`.
- Разработка: `docs/engineering/`.
- Harness: `AGENTS.md`, `.opencode/`, `.session-context.md`.

## Главные инварианты

- Не редактировать исторические ТЗ и ADR.
- Не коммитить и не push без разрешения пользователя.
- Плагин не пишет файлы сам; только возвращает `Artifact`.
- `GenerationContext` и входы плагина immutable/read-only.
- Ownership только через `.eggpipe/manifest.json`.
- EG033/EG034/EG301/EG302 — config/plugin errors, exit 2.
- `--plan`/`--check` не пишут файлы и не берут lock.
