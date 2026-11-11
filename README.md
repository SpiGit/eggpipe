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
from metadata_generator import Engine, AppConfig, GeneratorRulesLoader

rules = GeneratorRulesLoader().load(".mg.yaml")
engine = Engine(AppConfig(), rules)

report = engine.build()        # парсинг/валидация/генерация без записи
report = engine.generate()     # build + запись артефактов

if not report.success:
    for d in report.diagnostics:
        print(d.code, d.message)
```

`Engine` не вызывает `sys.exit`, не настраивает root-logger и не пишет файлы в `build()` — это обычная библиотека. Детали — System Design §2.8.

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
       id = "my-project-generator"
       name = "My Project Generator"

       def generate(self, input: GeneratorInput) -> GenerationResult:
           # input.model — замкнутый срез модели (ModelSlice: entities/enums/types)
           # input.context — variables, naming_hint, format, импортированные файлы
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

# Для watch-режима
pip install "metadata-generator[watch]"

# Инициализация конфигурации
mg init

# Генерация
mg generate model.yaml
mg generate --plan            # посмотреть план без записи
mg generate --check           # проверить актуальность (CI)

# Режим watch
mg watch model.yaml

# Разработка своего плагина — editable install
pip install -e ./plugins/my-generator
mg gen list
```

## Разработка

```bash
uv sync --extra dev

uv run ruff check .
uv run ruff format --check src tests tools
uv run pyrefly check
uv run pytest --cov
uv run python tools/check_docs.py --strict
uv build
uv run python tools/check_wheel.py dist
```

Dev/CI используют [uv](https://docs.astral.sh/uv/) и закоммиченный `uv.lock`.
Для установки пакета пользователями остаётся `pip install metadata-generator`.

Типизация — [Pyrefly](https://pyrefly.org/) в strict-режиме (встроенная поддержка Pydantic v2).
mypy не входит в блокирующий CI; решение зафиксировано в
[ADR-0002](./docs/adr/0002-type-checker-pyrefly.md).

Для basedpyright/Pyright в корне лежит `pyrightconfig.json` (src-layout, `extraPaths`, `.venv`).
Перед проверкой выполните `uv sync --extra dev`.

## Документация

Проверка согласованности документации:

```bash
uv run python tools/check_docs.py --strict
```

- [Техническое задание](./docs/requirements/index.md) — актуальная версия v1.2
- [System Design](./docs/system-design/index.md)
- [ADR-0001: семантика композиции](./docs/adr/0001-composition-merge-semantics.md)
- [ADR-0002: type checker — Pyrefly](./docs/adr/0002-type-checker-pyrefly.md)
- [Ревью проекта (2026-11-10)](./docs/reviews/2026-11-10-project-review.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

## Лицензия

[MIT](./LICENSE).

## Статус

**Стадия:** проектирование (draft) — следующий шаг: разработка ядра v0.1 (см. Roadmap в ТЗ v1.2 §13).
