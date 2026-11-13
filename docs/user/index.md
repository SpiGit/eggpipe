# Пользовательская документация

Eggpipe читает YAML-описание модели данных и генерирует артефакты через плагины.

## С чего начать

1. [Быстрый старт](quickstart.md) — установка и первый запуск.
2. [Tutorial: TPC-H](tutorial.md) — полный пример от модели до артефактов.
3. [Понятия](concepts.md) — model unit, формат, слой, срез, ownership.

## Справочники

- [Конфигурация](configuration.md) — все поля `.eggpipe.yaml`.
- [CLI](cli.md) — команды, флаги и exit codes.
- [API](api/index.md) — библиотечный API и плагины.
- [Плагины](plugins.md) — генераторы и форматы.
- [Диагностики](reference/diagnostics.md) — коды EGxxx.

## Практика

- [Cookbook](cookbook/index.md) — типовые рецепты.
- [Troubleshooting](troubleshooting.md) — что делать при ошибке.
- [FAQ](faq.md).

## Базовые понятия

- **Модель** — YAML-файл с `format`, `version` и секцией `model`.
- **Формат** — диалект модели: `entity-model` встроен, остальные подключаются плагинами.
- **Раскладка** — `monolith`, `file-per-model` или `directory-per-model`.
- **Срез** — подмножество модели для конкретного генератора.
- **Location** — пара `(generator, output_dir)`, которой принадлежат записанные файлы.
- **Manifest** — `.eggpipe/manifest.json`; хранит ownership и хэши.
