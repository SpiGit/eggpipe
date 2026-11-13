# AI tasks

Типовые задачи агента в Eggpipe и порядок действий.

## Добавить генератор

1. Прочитать `docs/engineering/requirements/v2.1.md` §6.1 и `docs/user/plugins.md`.
2. Создать функцию с `@generator(id=..., input_formats=...)`.
3. Аннотировать аргументы только `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
4. Вернуть `Artifact`, `list[Artifact]`, `tuple[Artifact, ...]` или `GenerationResult`.
5. Добавить entry point `[project.entry-points."eggpipe.generators"]`.
6. Добавить contract/golden-тест.
7. Прогнать `pytest`, `ruff`, `pyrefly`, `check_docs`.

## Добавить формат

1. Прочитать §3.4 и §6.2 ТЗ, ADR-0007.
2. Унаследовать `EntityModelFormat`.
3. Задать `format_names`, `supported_versions`, `extends`, `base_versions`,
   `primitive_types`, `schemas`.
4. Реализовать `parse_extensions`/`validate_extensions`, если нужны дополнительные поля.
5. Добавить тесты наследования, версий, latest-версии и MG034.
6. Проверить mixed formats и `input_formats` генератора (MG033).

## Разобрать диагностику

1. Найти код в `docs/user/reference/diagnostics.md`.
2. Найти место эмиссии: `rg "MG0xx"`.
3. Исправить причину, а не подавлять ошибку.
4. `ignore` применять только к warnings; errors не игнорируются.
5. Добавить регрессионный тест.

## Изменить поведение

1. Проверить, не описано ли оно в актуальном ТЗ.
2. Если поведение меняется — выпустить новую версию ТЗ, а не править текущую.
3. Обновить System Design/ADR при необходимости.
4. Обновить код и тесты.
5. Синхронизировать user/AI docs, README и session context.

## Перед завершением

```bash
uv run pytest --cov
uv run ruff check .
uv run ruff format --check src tests tools examples
uv run pyrefly check
uv run python tools/check_docs.py --strict
uv run mkdocs build --strict
uv build
uv run python tools/check_wheel.py dist
```
