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

Ключевые свойства:

- **Сущности изолированы**: базовая модель не знает о связях между ними — ядро остаётся нейтральным.
- **Нет встроенных генераторов**: все генераторы и все форматы (кроме базового `entity-model`) — плагины.
- **Модель — просто данные**: метаконфиг решает, что, из чего и куда генерировать.

## Режимы использования

### Как CLI

```bash
pip install metadata-generator
mg generate model.yaml
mg watch model.yaml
```

### Как библиотека

```python
from metadata_generator import Engine, AppConfig

# Programmatic API (детали — в System Design §2)
engine = Engine(AppConfig(), rules)
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

2. Плагин генерации:
   ```python
   # my_project/plugins.py
   from metadata_generator import GeneratorPlugin, GeneratorInput, GenerationResult, Artifact

   class MyProjectGenerator(GeneratorPlugin):
       api_version = "1"

       @property
       def id(self) -> str:
           return "my-project-generator"

       def generate(self, input: GeneratorInput) -> GenerationResult:
           # input.model — цельный срез модели (entities/enums/types)
           # input.context — vars, naming-fit, импортированные файлы
           # input.config — блок этого генератора из .mg.yaml
           return GenerationResult(artifacts=[
               Artifact(path="user.py", content=render(input.model.entities...))
           ])
   ```

3. Регистрация через entry points:
   ```toml
   # pyproject.toml проекта N
   [project.entry-points."metadata_generator.generators"]
   my-project-generators = "my_project.plugins:MyProjectGenerator"
   ```

4. Запуск:
   - CLI: `mg generate` — обнаруживает плагины из entry points
   - Library: `engine.generate()` — тот же результат

**Примеры инструментов с такой архитектурой:** ruff, pytest, mypy.

Плагин также может регистрировать **формат документа** (например `sql-model` с SQL-спецификой и собственными правилами) — группа entry points `metadata_generator.formats`.

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

# Разработка своего плагина — editable install
pip install -e ./plugins/my-generator
mg gen list
```

## Документация

- [Техническое задание](./docs/requirements/index.md) — актуальная версия v1.1
- [System Design](./docs/system-design/index.md)
- [ADR-0001: семантика композиции](./docs/adr/0001-composition-merge-semantics.md)

## Статус

**Стадия:** проектирование (draft) — следующий шаг: разработка ядра v0.1 (см. Roadmap в ТЗ v1.1 §13).
