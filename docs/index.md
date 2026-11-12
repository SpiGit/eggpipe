# Metadata Generator

Документация проекта `metadata-generator` — генерация артефактов из YAML-описания модели данных.

## Навигация

- [Технические требования](requirements/index.md) — актуальное ТЗ v1.4 и история версий.
- [System Design](system-design/index.md) — проектирование реализации.
- [ADR](adr/index.md) — принятые архитектурные решения.
- [Руководство по плагинам](plugin-guide.md) — генераторы и форматы.
- [Каталог диагностик](reference/diagnostics.md) — коды MGxxx.
- [Релиз](release.md) — чек-лист и публикация.
- [Ревью проекта](reviews/2026-11-10-project-review.md) — P0/P1/P2 backlog.

## Быстрый старт

```bash
uv sync --extra dev
mg model validate ./models/blog.yaml
mg generate -c .mg.yaml
mg generate -c .mg.yaml --plan
mg generate -c .mg.yaml --check
```

Полный README и примеры — в корне репозитория.
