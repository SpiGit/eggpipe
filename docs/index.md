# Eggpipe

Документация проекта `eggpipe` — генерация артефактов из YAML-описания модели данных.

## Навигация

- [Технические требования](requirements/index.md) — актуальное ТЗ v2.0 и история версий.
- [Eggpipe](eggpipe.md) — выбранное имя, история подбора и идеи для лого.
- [План v2.0](plan-v2.md) — эпики, зависимости и критерии готовности.
- [Ревью v2.0](reviews/2026-11-12-v2-review.md) — результаты проверки документации.
- [System Design](system-design/index.md) — проектирование реализации.
- [ADR](adr/index.md) — принятые архитектурные решения.
- [Руководство по плагинам](plugin-guide.md) — генераторы и форматы.
- [Каталог диагностик](reference/diagnostics.md) — коды MGxxx.
- [Релиз](release.md) — чек-лист и публикация.
- [Ревью проекта](reviews/2026-11-10-project-review.md) — P0/P1/P2 backlog.

## Быстрый старт

```bash
uv sync --extra dev
eggpipe model validate ./models/blog.yaml
eggpipe generate -c .eggpipe.yaml
eggpipe generate -c .eggpipe.yaml --plan
eggpipe generate -c .eggpipe.yaml --check
```

Полный README и примеры — в корне репозитория.
