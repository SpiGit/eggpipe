# System Design — Metadata Generator

> Документ реализации (implementation details) для проекта metadata-generator.

---

## 1. Обзор архитектуры

### 1.1 Компоненты и их ответственность

```
┌─────────────────────────────────────────────────────────────────┐
│                      metadata-generator (ядро)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CLI ──▶ Config ──▶ Engine ──▶ Model Builder                   │
│                          │                                       │
│              ┌───────────┼───────────┐                          │
│              ▼           ▼           ▼                          │
│          Parser    Composition    Validator                     │
│                                                                  │
│   Plugin Loader ←──────────────────────                          │
│        │                                                        │
│        ▼                                                        │
│   Plugins (генераторы)                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Компонент | Ответственность |
|-----------|-----------------|
| **CLI** | Парсинг аргументов, вывод результатов, watch mode |
| **Config** | Загрузка Application Config (env vars, .env, defaults) |
| **Engine** | Orchestration: координация парсинга, загрузки плагинов, запуска генерации |
| **Parser** | Парсинг YAML, imports, extends |
| **Composition** | Объединение данных из нескольких файлов |
| **Validator** | Валидация модели (типы, ссылки, циклы) |
| **Plugin Loader** | Загрузка плагинов-генераторов |
| **Plugins** | Генерация артефактов (код + шаблоны внутри плагина) |

### 1.2 Поток данных

```
1. CLI получает команду (mg generate, -g, model.yaml, etc.)
        │
        ▼
2. Config загружает Application Config (env → .env → defaults)
        │
        ▼
3. Engine загружает Business Config (.mg.yaml)
        │
        ▼
4. Для каждого source в .mg.yaml:
    ├── Parser парсит YAML
    ├── Composition объединяет imports
    └── Validator валидирует
        │
        ▼
5. Model Builder собирает единую модель
        │
        ▼
6. Plugin Loader загружает указанные генераторы
        │
        ▼
7. Для каждого генератора:
    ├── Engine передаёт Model + GeneratorConfig
    └── Plugin.generate() → [Artifact]
        │
        ▼
8. Artifact Writer записывает артефакты
        │
        ▼
9. CLI выводит результат
```

---

## 2. Интерфейс плагина (GeneratorPlugin)

### 2.1 Контракт: что плагин получает

```python
# Ядро передаёт плагину:
class GeneratorInput(BaseModel):
    """Входные данные для генератора."""
    model: SourceModel           # Распарсенная модель
    config: GeneratorConfig      # Конфиг генератора из .mg.yaml
    app_config: AppConfig        # Application Config (technical settings)
    context: GenerationContext   # Дополнительный контекст
```

### 2.2 Контракт: что плагин возвращает

```python
class Artifact(BaseModel):
    """Один сгенерированный файл."""
    path: str                    # Относительный путь файла
    content: str                 # Содержимое файла
    mime_type: str               # MIME-тип (application/sql, text/x-python, etc.)

class GenerationResult(BaseModel):
    """Результат генерации."""
    artifacts: list[Artifact] = []
    warnings: list[str] = []     # Предупреждения (не критичные)
    errors: list[str] = []       # Ошибки генерации

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
```

### 2.3 Базовый интерфейс

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class GeneratorPlugin(ABC):
    """Базовый интерфейс плагина-генератора."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Уникальный идентификатор генератора."""
        ...

    @property
    def name(self) -> str:
        """Человекочитаемое имя для вывода."""
        return self.id

    @property
    def supported_formats(self) -> list[str]:
        """Какие format документа поддерживает (entity-model, sql-model, etc.)."""
        return []

    @abstractmethod
    def generate(
        self,
        input: GeneratorInput,
    ) -> GenerationResult:
        """Основной метод генерации."""
        ...

    def validate_config(self, config: GeneratorConfig) -> list[str]:
        """Валидация конфига генератора. Возвращает список ошибок."""
        return []
```

### 2.4 Жизненный цикл

```
init()           → __init__ плагина (опционально)
validate_config() → Проверка .mg.yaml конфига (опционально)
generate()        → Основная генерация
cleanup()         → Очистка (если нужно, опционально)
```

### 2.5 Пример реализации плагина

```python
# my-generator/src/my_generator/__init__.py

from metadata_generator.core import GeneratorPlugin, GeneratorInput, GenerationResult, Artifact

class MyGenerator(GeneratorPlugin):
    @property
    def id(self) -> str:
        return "my-generator"

    @property
    def name(self) -> str:
        return "My Custom Generator"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        artifacts = []

        for entity in input.model.entities:
            content = self._render_entity(entity, input)
            artifacts.append(Artifact(
                path=f"{entity.name.lower()}.py",
                content=content,
                mime_type="text/x-python"
            ))

        return GenerationResult(artifacts=artifacts)

    def _render_entity(self, entity, input):
        # Рендеринг через Jinja2 или свой движок
        template = self._get_template("entity.j2")
        return template.render(entity=entity, config=input.config)
```

---

## 3. Внутренние структуры ядра (Pydantic)

> Все внутренние модели используют **Pydantic v2** для валидации, сериализации и автогенерации ошибок.

### 3.1 SourceModel — модель данных

```python
from pydantic import BaseModel, Field, field_validator
from typing import Any

# Примитивные типы (из ТЗ)
PRIMITIVE_TYPES = {"string", "int", "float", "bool", "datetime", "date", "text"}

class Constraints(BaseModel):
    """Ограничения поля."""
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

class Field(BaseModel):
    """Поле сущности."""
    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: str
    description: str | None = None
    required: bool = False
    nullable: bool = True
    default: str | int | float | bool | None = None
    constraints: Constraints | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        # Тип может быть примитивом или ссылкой на enum/type
        # Валидация ссылок происходит на уровне Composition
        return v

class Import(BaseModel):
    """Импортированный файл."""
    path: Path
    content: bytes
    as_name: str | None = None

class Entity(BaseModel):
    """Сущность."""
    name: str = Field(..., min_length=1)
    description: str | None = None
    fields: list[Field] = []
    imports: dict[str, Import] = {}    # name → Import
    metadata: dict[str, Any] = {}      # Произвольные метаданные

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v[0].isupper():
            raise ValueError("Entity name must start with uppercase")
        return v

class EnumValue(BaseModel):
    """Значение перечисления."""
    name: str = Field(..., min_length=1)
    value: str | int
    description: str | None = None

class Enum(BaseModel):
    """Перечисление."""
    name: str = Field(..., min_length=1)
    description: str | None = None
    values: list[EnumValue] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v[0].isupper():
            raise ValueError("Enum name must start with uppercase")
        return v

class CustomType(BaseModel):
    """Пользовательский тип."""
    name: str = Field(..., min_length=1)
    base: str                          # Базовый примитивный тип
    constraints: Constraints | None = None

class SourceModel(BaseModel):
    """Распарсенная модель — внутреннее представление."""
    name: str
    description: str | None = None
    entities: list[Entity] = []
    enums: list[Enum] = []
    types: list[CustomType] = []
    metadata: dict[str, Any] = {}

    @property
    def entity_map(self) -> dict[str, Entity]:
        """Быстрый доступ к сущностям по имени."""
        return {e.name: e for e in self.entities}

    @property
    def enum_map(self) -> dict[str, Enum]:
        """Быстрый доступ к enum'ам по имени."""
        return {e.name: e for e in self.enums}
```

### 3.2 GeneratorConfig — конфиг генератора

```python
class GeneratorInputConfig(BaseModel):
    """Что брать из source."""
    entities: list[str] | None = None   # Пусто = все
    enums: list[str] | None = None
    types: list[str] | None = None

class GeneratorConfig(BaseModel):
    """Конфиг генератора из .mg.yaml."""
    id: str = Field(..., min_length=1)
    enabled: bool = True
    source: str                        # Путь к source
    input: GeneratorInputConfig = GeneratorInputConfig()
    output_dir: str
    file_naming: str | None = None
    options: dict[str, Any] | None = None
    templates: dict[str, str] | None = None
```

### 3.3 BusinessConfig — .mg.yaml

```python
class DefaultsConfig(BaseModel):
    """Defaults для генерации."""
    naming_convention: str = "snake_case"
    required_by_default: bool = False

class SourceConfig(BaseModel):
    """Источник данных."""
    path: str
    entities: list[str] | None = None   # Пусто = все
    enums: list[str] | None = None
    types: list[str] | None = None

class BusinessConfig(BaseModel):
    """Содержимое .mg.yaml."""
    version: str = "1.0"
    defaults: DefaultsConfig = DefaultsConfig()
    sources: list[SourceConfig] = []
    generators: list[GeneratorConfig] = []
```

### 3.4 Преимущества Pydantic

| Возможность | Как работает |
|-------------|--------------|
| **Валидация типов** | Автоматически при создании модели |
| **YAML → Model** | `SourceModel.model_validate(yaml_data)` |
| **Понятные ошибки** | `e.error_count()`, `e.errors()` |
| **Aliases** | `Field(validation_alias="...")` для kebab-case YAML |
| **Defaults** | `Field(default_factory=list)` |
| **Computed fields** | `@computed_field` для `entity_map` |

### 3.5 Парсинг YAML с валидацией

```python
def parse_model(yaml_data: dict) -> SourceModel:
    """Парсит YAML в SourceModel с валидацией."""
    try:
        return SourceModel.model_validate(yaml_data)
    except ValidationError as e:
        # Pydantic 自动но формирует понятные ошибки
        for error in e.errors():
            print(f"{error['loc']}: {error['msg']}")
        raise
```

---

## 4. Парсинг YAML

### 4.1 Parser

```python
class Parser:
    """Парсит YAML-документы в SourceModel."""

    def __init__(self, format_registry: FormatRegistry):
        self.format_registry = format_registry

    def parse(self, path: Path) -> SourceModel:
        """Парсит документ по пути."""
        with open(path) as f:
            data = yaml.safe_load(f)

        format_type = data.get("format", "entity-model")
        parser = self.format_registry.get_parser(format_type)

        return parser.parse(data, base_path=path.parent)

    def parse_with_composition(self, path: Path) -> SourceModel:
        """Парсит документ с учетом imports и extends."""
        doc = self.parse(path)

        # Обработка imports
        doc = self._resolve_imports(doc, path.parent)

        # Обработка extends
        doc = self._resolve_extends(doc, path.parent)

        return doc
```

### 4.2 Resolution imports

```python
    def _resolve_imports(self, doc: dict, base_path: Path) -> dict:
        """Рекурсивно разрешает imports."""
        imports = doc.get("model", {}).get("imports", [])

        for imp in imports:
            imp_path = (base_path / imp["path"]).resolve()
            imp_doc = self.parse_with_composition(imp_path)

            # Мержим данные
            doc = self._merge(doc, imp_doc)

        return doc

    def _merge(self, target: dict, source: dict) -> dict:
        """Мержит source в target. source приоритетнее."""
        # Рекурсивный мерж списков (entities, enums) по name
        # Перезапись полей при совпадении name
        ...
```

### 4.3 Resolution extends

```python
    def _resolve_extends(self, doc: dict, base_path: Path) -> dict:
        """Обрабатывает extends для типов документа."""
        extends = doc.get("extends")

        if not extends:
            return doc

        # Загружаем родительский тип
        parent_path = self._find_type_definition(extends)
        parent_doc = self.parse_with_composition(parent_path)

        # Мержим: parent → child (child приоритетнее)
        return self._merge(parent_doc, doc)
```

---

## 5. Configuration Layer

### 5.1 Application Config (pydantic-settings)

```python
# metadata_generator/config.py

from pydantic_settings import BaseSettings
from pathlib import Path

class AppConfig(BaseSettings):
    """Application Config — технические настройки."""

    # Логирование
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_destination: str = "stderr"    # stderr, stdout, file:path

    # Пути
    plugins_dir: Path = Path("./plugins")
    cache_dir: Path = Path(".mg-cache")
    config_file: Path | None = None    # Путь к .mg.yaml

    # Debug
    debug: bool = False
    verbose: bool = False
    quiet: bool = False

    # Watch
    watch_debounce_ms: int = 300

    class Config:
        env_prefix = "MG_"
        env_file = ".env"
        env_nested_delimiter = "_"
```

### 5.2 Загрузка Business Config

```python
class BusinessConfigLoader:
    """Загружает и валидирует .mg.yaml через Pydantic."""

    def load(self, path: Path) -> BusinessConfig:
        """Загружает .mg.yaml."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Pydantic валидирует автоматически
        try:
            return BusinessConfig.model_validate(data)
        except ValidationError as e:
            raise ConfigValidationError.from_pydantic(e)

    def load_from_dir(self, dir: Path) -> BusinessConfig | None:
        """Ищет .mg.yaml в директории."""
        config_path = dir / ".mg.yaml"
        if config_path.exists():
            return self.load(config_path)
        return None

class ConfigValidationError(Exception):
    """Ошибка валидации конфигурации."""

    @classmethod
    def from_pydantic(cls, e: ValidationError) -> "ConfigValidationError":
        messages = []
        for error in e.errors():
            loc = " → ".join(str(l) for l in error["loc"])
            messages.append(f"{loc}: {error['msg']}")
        return cls("\n".join(messages))
```

### 5.3 Aliases для YAML (kebab-case → snake_case)

```python
from pydantic import ConfigDict, Field

class GeneratorConfig(BaseModel):
    """Поддержка kebab-case в YAML."""
    model_config = ConfigDict(populate_by_name=True)

    generator_id: str = Field(alias="generator-id")
    output_dir: str = Field(alias="output-dir")
    file_naming: str | None = Field(None, alias="file-naming")

# YAML:
# generator-id: my-gen
# output-dir: ./output
# file-naming: kebab

# Превращается в:
# GeneratorConfig(generator_id="my-gen", output_dir="./output", file_naming="kebab")
```

---

## 6. Plugin Loader

### 6.1 Механизм загрузки

```python
class PluginLoader:
    """Загружает плагины-генераторы."""

    def __init__(self, app_config: AppConfig):
        self.app_config = app_config
        self._plugins: dict[str, GeneratorPlugin] = {}

    def discover(self) -> dict[str, GeneratorPlugin]:
        """Обнаруживает и загружает все доступные плагины."""
        # 1. Entry points (из установленных пакетов)
        self._load_from_entry_points()

        # 2. Локальные плагины из plugins_dir
        if self.app_config.plugins_dir.exists():
            self._load_from_directory(self.app_config.plugins_dir)

        return self._plugins

    def _load_from_entry_points(self):
        """Загрузка через pip entry_points."""
        for ep in importlib.metadata.entry_points(
            group="metadata_generator.generators"
        ):
            plugin_class = ep.load()
            plugin = plugin_class()
            self._plugins[plugin.id] = plugin

    def _load_from_directory(self, plugins_dir: Path):
        """Загрузка локальных плагинов."""
        for item in plugins_dir.iterdir():
            if item.is_dir() and (item / "pyproject.toml").exists():
                # Добавляем в sys.path и загружаем
                ...
```

### 6.2 Регистрация плагина (pyproject.toml)

```toml
# Пример: my-generator/pyproject.toml

[project]
name = "my-generator"
version = "1.0.0"

[project.entry-points."metadata_generator.generators"]
my-generator = "my_generator:MyGenerator"
```

---

## 7. CLI (Typer)

### 7.1 Структура команд

```python
# metadata_generator/cli/main.py

import typer

app = typer.Typer(name="mg", help="Metadata Generator")

@app.command()
def generate(
    models: list[str] = typer.Argument(None, help="Пути к моделям"),
    generator: list[str] = typer.Option(None, "-g", "--generator", help="Генераторы"),
    config: Path = typer.Option(None, "-c", "--config", help="Путь к .mg.yaml"),
    output: Path = typer.Option(None, "-o", "--output", help="Output dir"),
    watch: bool = typer.Option(False, "-w", "--watch", help="Watch mode"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    format: str = typer.Option("text", "--format", help="text или json"),
):
    """Генерация артефактов."""
    ...

@app.command()
def init():
    """Создать шаблон .mg.yaml."""
    ...

@app.command()
def config_show(config: Path = typer.Option(".mg.yaml")):
    """Показать конфигурацию."""
    ...

@app.command()
def list_generators():
    """Список доступных генераторов."""
    ...
```

### 7.2 Output Formatters

```python
class OutputFormatter(ABC):
    @abstractmethod
    def format(self, result: GenerationResult) -> str:
        ...

class TextFormatter(OutputFormatter):
    def format(self, result: GenerationResult) -> str:
        # [✓] generator → path/
        #     ├── file1
        #     └── file2
        ...

class JsonFormatter(OutputFormatter):
    def format(self, result: GenerationResult) -> str:
        return json.dumps({
            "success": True,
            "artifacts": [...],
            "warnings": [...],
        }, indent=2)
```

---

## 8. Watch Mode

### 8.1 File Watcher

```python
# Простой watch без кэширования
class Watcher:
    """Наблюдает за изменениями файлов."""

    def __init__(self, paths: list[Path], callback: Callable, debounce_ms: int = 300):
        self.paths = paths
        self.callback = callback
        self.debounce_ms = debounce_ms

    def start(self):
        """Запускает наблюдение."""
        from watchdog.observers import Observer

        observer = Observer()
        for path in self.paths:
            event_handler = DebounceHandler(
                callback=self.callback,
                debounce_ms=self.debounce_ms
            )
            observer.schedule(event_handler, str(path), recursive=True)

        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

class DebounceHandler(FileSystemEventHandler):
    """Handler с debounce."""

    def __init__(self, callback: Callable, debounce_ms: int):
        self.callback = callback
        self.debounce_ms = debounce_ms
        self._timers: dict[str, Timer] = {}

    def on_modified(self, event):
        # Debounce: ждём debounce_ms после последнего изменения
        path = event.src_path
        if path in self._timers:
            self._timers[path].cancel()

        self._timers[path] = Timer(self.debounce_ms / 1000, self.callback, [path])
        self._timers[path].start()
```

### 8.2 Интерфейс для будущего кэширования

```python
# Заложено для future расширения
class CacheStrategy(ABC):
    """Интерфейс для кэширования."""

    @abstractmethod
    def get_hash(self, path: Path) -> str:
        """Получить хеш файла."""
        ...

    @abstractmethod
    def is_changed(self, path: Path) -> bool:
        """Проверить, изменился ли файл."""
        ...

    @abstractmethod
    def get_dependencies(self, path: Path) -> list[Path]:
        """Получить зависимости файла (для cascade invalidation)."""
        ...
```

---

## 9. Структура проекта (код)

### 9.1 Ядро

```
metadata-generator/                    # pip пакет
├── src/metadata_generator/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                   # Точка входа (typer)
│   │   ├── commands.py               # Команды (generate, init, etc.)
│   │   └── formatters.py             # TextFormatter, JsonFormatter
│   ├── core/
│   │   ├── __init__.py
│   │   ├── model.py                  # SourceModel, Entity, Field, Constraints (Pydantic)
│   │   ├── parser.py                 # Parser, YamlParser
│   │   └── composition.py            # Merge, resolve imports/extends
│   ├── config/
│   │   ├── __init__.py
│   │   ├── app_config.py             # AppConfig (pydantic-settings)
│   │   ├── business_config.py        # BusinessConfigLoader
│   │   └── schemas/
│   │       └── metacofig.schema.json # JSON Schema для .mg.yaml
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── engine.py                 # Engine orchestration
│   │   ├── plugin_loader.py          # PluginLoader
│   │   └── artifact_writer.py        # ArtifactWriter
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── generator.py              # GeneratorPlugin, GenerationResult, etc.
│   ├── watch/
│   │   ├── __init__.py
│   │   ├── watcher.py                # Watcher, DebounceHandler
│   │   └── cache.py                  # CacheStrategy (interface)
│   └── utils/
│       ├── __init__.py
│       └── logging.py
├── tests/
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_composition.py
│   │   └── test_config.py
│   ├── integration/
│   │   └── test_generate.py
│   └── fixtures/
│       └── models/
├── docs/
│   ├── requirements/
│   ├── system-design/
│   └── user-guide/
├── pyproject.toml
├── README.md
└── LICENSE
```

### 9.2 Пример плагина

```
my-generator/                         # pip пакет
├── src/my_generator/
│   ├── __init__.py                   # MyGenerator (GeneratorPlugin)
│   ├── renderer.py                   # Логика рендеринга
│   └── templates/                    # Шаблоны
│       ├── entity.j2
│       └── index.j2
├── tests/
├── pyproject.toml                    # entry point
└── README.md
```

---

## 10. Тестирование

### 10.1 Структура тестов

```python
# tests/unit/test_parser.py
class TestParser:
    def test_parse_simple_model(self):
        """Парсинг простой модели."""
        ...

    def test_parse_with_imports(self):
        """Парсинг с imports."""
        ...

    def test_parse_with_extends(self):
        """Парсинг с extends."""
        ...

    def test_cyclic_import_error(self):
        """Ошибка при циклических imports."""
        ...

# tests/unit/test_composition.py
class TestComposition:
    def test_merge_entities(self):
        """Мерж сущностей из разных файлов."""
        ...

    def test_inheritance_fields(self):
        """Наследование полей через extends."""
        ...
```

### 10.2 Property-based тесты

```python
# tests/property/test_parser.py
from hypothesis import given, strategies as st

class TestParserPropertyBased:
    @given(st.dictionaries(st.text(), st.text()))
    def test_valid_yaml_parsing(self, data):
        """Любой валидный YAML парсится без падения."""
        ...

    @given(valid_model_data())
    def test_round_trip(self, data):
        """Модель → YAML → модель консистентна."""
        ...
```

### 10.3 Integration тесты

```python
# tests/integration/test_generate.py
class TestGenerate:
    def test_full_pipeline(self, tmp_path):
        """Полный цикл: модель → генерация → артефакты."""
        # Создаём модель
        # Создаём .mg.yaml
        # Запускаем mg generate
        # Проверяем артефакты
        ...
```

---

## 11. Зависимости (pyproject.toml)

```toml
[project]
name = "metadata-generator"
version = "0.1.0"
description = "CLI tool for metadata-driven code generation"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0.1",
    "watchdog>=3.0.0",
    "rich>=13.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.92.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
mg = "metadata_generator.cli.main:app"

[project.entry-points."metadata_generator.generators"]
# Плагины подключаются через свои пакеты
```

---

*Версия документа: 1.0*  
*Дата: 2025-11-03*
