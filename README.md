# Metadata Generator

> Инструмент для генерации артефактов (SQL, Python, TypeScript, etc.) из YAML-описания модели данных.

## Концепция

**Один источник истины → произвольные форматы вывода.**

Описываете структуру данных один раз в YAML — получаете:
- SQL-миграции и схемы
- Python-модели (Pydantic, Django, SQLAlchemy, dataclasses)
- TypeScript-типы и Zod-схемы
- OpenAPI-спецификации
- Go-структуры
- И всё остальное через плагинную систему

## Режимы использования

### Как CLI

```bash
pip install metadata-generator
mg generate model.yaml
mg watch model.yaml
```

### Как библиотека

```python
from metadata_generator.core import Engine
from metadata_generator.config import AppConfig

# Programmatic API
engine = Engine(config)
results = engine.generate()
```

### Как библиотека + CLI (рекомендуемый сценарий)

**Сценарий:** Проект N подключает metadata-generator как библиотеку, пишет свои плагины генерации, запускает через CLI.

1. Подключение как зависимость:
   ```toml
   # pyproject.toml проекта N
   [project]
   dependencies = ["metadata-generator"]
   ```

2. Плагины генерации в проекте N:
   ```python
   # my_project/plugins/__init__.py
   from metadata_generator.core import GeneratorPlugin, GeneratorInput, GenerationResult
   
   class MyProjectGenerator(GeneratorPlugin):
       @property
       def id(self) -> str:
           return "my-project-generator"
       
       def generate(self, entity: GeneratorInput, context) -> GenerationResult:
           # Генерируем всё что нужно для проекта N
           return GenerationResult(...)
   ```

3. Регистрация через entry points:
   ```toml
   # pyproject.toml проекта N
   [project.entry-points."metadata_generator.generators"]
   my-project = "my_project.plugins:MyProjectGenerator"
   ```

4. Запуск:
   - CLI: `mg generate` — обнаруживает плагины из entry points
   - Library: `engine.generate()` — тот же результат

**Примеры инструментов с такой архитектурой:** ruff, pytest, mypy.

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
