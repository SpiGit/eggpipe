# Metadata Generator

> CLI-инструмент для генерации артефактов (SQL, Python, TypeScript, etc.) из YAML-описания модели данных.

## Концепция

**Один источник истины → произвольные форматы вывода.**

Описываете структуру данных один раз в YAML — получаете:
- SQL-миграции и схемы
- Python-модели (Pydantic, Django, SQLAlchemy, dataclasses)
- TypeScript-типы и Zod-схемы
- OpenAPI-спецификации
- Go-структуры
- И всё остальное через плагинную систему

## Быстрый старт

```bash
# Установка (после реализации)
pip install metadata-generator

# Инициализация конфигурации
mg init

# Генерация
mg generate model.yaml

# Режим watch
mg watch model.yaml
```

## Документация

- [Техническое задание](./docs/requirements/index.md)

## Статус

**Стадия:** проектирование (draft)

См. [текущее ТЗ](./docs/requirements/index.md#открытые-вопросы-для-уточнения) для списка открытых вопросов.
