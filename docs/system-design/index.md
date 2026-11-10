# System Design — Metadata Generator

> Документ реализации для проекта metadata-generator. Соответствует [ТЗ v1.1](../requirements/v1.1.md). Правила композиции — [ADR-0001](../adr/0001-composition-merge-semantics.md).

*Версия документа: 1.1. Дата: 2026-11-10.*

---

## 1. Обзор архитектуры

### 1.1 Компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│                      metadata-generator (ядро)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CLI ──▶ Config ──▶ Engine ──▶ Model Builder                    │
│                          │                                       │
│              ┌───────────┼───────────┐                          │
│              ▼           ▼           ▼                          │
│   FormatRegistry  Parser  Composition  Validator                 │
│                                                                  │
│   Plugin Loader (entry points: generators + formats)             │
│        │                                                        │
│        ▼                                                        │
│   Плагины (генераторы + доп. форматы)                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Компонент | Ответственность |
|-----------|-----------------|
| **CLI** | Парсинг аргументов, вывод результатов, watch mode |
| **Config** | AppConfig (env → .env → defaults) + GeneratorRules (.mg.yaml) |
| **Engine** | Оркестрация: парсинг → composition → validate → generate → write |
| **FormatRegistry** | Реестр форматов: встроенный `entity-model` + форматы от формат-плагинов |
| **Parser** | YAML parse, imports, entity.extends |
| **Composition** | Merge по правилам ADR-0001 |
| **Validator** | Кросс-сущностные проверки: warnings + errors (null-matrix, дубликаты, unused, stale dates) |
| **Plugin Loader** | Загрузка плагинов из entry points, проверка `api_version` |
| **Artifact Writer** | Проверка путей, on_conflict, atomic write, manifest, cleanup |
| **Plugins** | Генераторы (и формат-плагины) — код + шаблоны |

### 1.2 Поток данных

```
1. CLI получает команду
        │
2. AppConfig создаётся (env → .env → defaults)
        │
3. GeneratorRulesLoader загружает .mg.yaml
        │
4. Для каждого source:
    ├── FormatRegistry выбирает формат (по header `format`)
    ├── Parser парсит YAML (imports, entity.extends — рекурсивно,
    │   правила merge: ADR-0001)
    └── Validator: структурные (Pydantic) + semantic проверки
        │
5. Engine собирает финальную модель из sources (union),
   валидирует глобальные инварианты (дубликаты имён между source)
        │
6. Plugin Loader загружает генераторы (проверка api_version)
        │
7. Для каждого генератора:
    ├── Engine вычисляет срез (sources × input)
    ├── формирует GeneratorInput (model, context, config)
    ├── Plugin.generate() → GenerationResult
    └── ArtifactWriter пишет артефакты (atomic, on_conflict, manifest)
        │
8. CLI выводит результат (text / json), exit code по §8.4 ТЗ
```

---

## 2. Интерфейсы плагинов

> Публичный API ядра экспортирует **только** эти контракты (из `metadata_generator.__init__`): `GeneratorPlugin, GeneratorInput, GenerationResult, Artifact, GenerationContext, ImportedFile, SourceModel, Entity, Field, Enum, CustomType, NamingStyle`. Всё остальное — внутреннее и может меняться.

### 2.1 GeneratorInput — вход генератора

```python
class GeneratorInput(BaseModel):
    """Замороженные входные данные генератора."""
    model: SourceModel           # цельный срез модели: entities/enums/types по sources × input
    config: GeneratorConfig      # свой блок из .mg.yaml (id, options, output_dir, ...)
    context: GenerationContext   # vars, naming hint, imported files, source paths
```

**AppConfig в плагин не передаётся** — технические настройки вне клиентского контракта.

### 2.2 GenerationContext

```python
class GenerationContext(BaseModel):
    """Контекст генерации, одинаковый для всех плагинов в запуске."""
    variables: dict[str, str] = {}      # --var ∪ .mg.yaml variables (CLI > config)
    naming_hint: NamingStyle | None     # defaults.naming_convention (подсказка!)
    imports: dict[str, ImportedFile]    # имя (as) → файл
    sources: list[Path]                 # пути source-файлов (провенанс)

class ImportedFile(BaseModel):
    name: str          # значение `as` из imports
    path: Path
    content: bytes     # ядро читает; decode — задача плагина
```

### 2.3 Artifact и GenerationResult — выход генератора

```python
class Artifact(BaseModel):
    """Один сгенерированный файл."""
    path: str                    # ОТНОСИТЕЛЬНЫЙ POSIX-путь; плагин сам решает имя
    content: str                 # текст; encoding = "utf-8"
    description: str | None = None

class GenerationResult(BaseModel):
    artifacts: list[Artifact] = []
    warnings: list[str] = []
    errors: list[str] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
```

mime_type убран: целиком артефакт — текст; ядро никакого прочего использования этого поля не имеет.

### 2.4 GeneratorPlugin

```python
from abc import ABC, abstractmethod
from typing import Literal

API_VERSION = Literal["1"]

class GeneratorPlugin(ABC):
    api_version: Literal["1"]          # ядро проверяет при загрузке
    id: str                            # совпадает с entry point id
    name: str = ""                     # default → id

    @abstractmethod
    def generate(self, input: GeneratorInput) -> GenerationResult: ...

    def validate_config(self, config: GeneratorConfig) -> list[str]:
        return []                      # semantic-ошибки конфига генератора
```

**Жизненный цикл:** `__init__` → `validate_config()` → `generate()`. `cleanup()` не в v1 (по необходимости — контекстный менеджер в future).

Замечание по многоразовости: экземпляр плагина создаётся один раз на запуск и не обязан быть потокобезопасным (v0.1–v0.2 — однопоточно).

### 2.5 FormatPlugin

```python
class FormatPlugin(ABC):
    """Регистрирует формат документа в FormatRegistry."""
    api_version: Literal["1"]
    format_names: list[str]            # ["sql-model", ...]
    supported_versions: list[str]      # ["1.0", "1.1"]

    @abstractmethod
    def parse(self, raw: dict, base_path: Path) -> SourceModel:
        """Парсит документ. Базовая реализация ядра покрывает entity-model;
        формат-плагин может использовать ядро и расширять."""


    def validate(self, model: SourceModel) -> list[Diagnostic]:
        """Формат-специфичные проверки (напр. column.generated для sql-model)."""
        return []
```

Формат-плагин ответственен за то, что документ его формата обязательно включает header поля `format`, `version` и поддерживаемую им версию; несовместимая версия → Diagnostic error.

### 2.6 NamingStyle

```python
class NamingStyle(StrEnum):
    SNAKE = "snake_case"
    CAMEL = "camelCase"
    PASCAL = "pascal_case"
    KEBAB = "kebab-case"

def transform(name: str, style: NamingStyle) -> str: ...
```

- `defaults.naming_convention` из `.mg.yaml` — **подсказка**: ядро кладёт её в `context.naming_hint` и никогда не переименовывает канонические имена (Entity.name остаётся как в YAML).
- Какую трансформацию куда применить — решает плагин (SQL table → snake, Pydantic class → pascal и т.п.).

### 2.7 Пример генератора

```python
# my-generator/src/my_generator/__init__.py
from metadata_generator import (
    GeneratorPlugin, GeneratorInput, GenerationResult, Artifact,
    NamingStyle, transform,
)

class MyGenerator(GeneratorPlugin):
    api_version = "1"

    @property
    def id(self) -> str:
        return "my-generator"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        result = GenerationResult()
        style = input.context.naming_hint or NamingStyle.SNAKE

        for entity in input.model.entities:
            content = self._render_entity(entity, input)
            result.artifacts.append(Artifact(
                path=f"{transform(entity.name, style)}.py",   # путь задаёт плагин
                content=content,
            ))

        # cross-entity артефакт — возможен, потому что вход цельный:
        result.artifacts.append(Artifact(path="__init__.py", content="# barrel"))
        return result
```

---

## 3. Внутренние модели ядра (Pydantic v2)

### 3.1 SourceModel

```python
PRIMITIVE_TYPES = Literal[
    "string", "text", "integer", "bigint", "boolean",
    "float", "date", "datetime", "uuid", "json",
]   # строго соответствует ТЗ §3.2 (не отдельный сет!)

class Constraints(BaseModel):
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None       # noqa — валидация regex в validator.py (warnings/error)

class Field(BaseModel):
    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: str
    description: str | None = None
    required: bool = False
    nullable: bool = False           # v1: НЕ nullable по умолчанию
    default: str | int | float | bool | None = None
    constraints: Constraints | None = None
    # default: scalar only. Никаких `auto`/`generated` — это зона формата-плагина.

class Entity(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    version: str | int | None = None          # опциональная версия сущности
    updated_at: datetime | None = None        # опциональная дата изменения сущности
    extends: str | None = None                # resolve в composition
    fields: list[Field] = []
    metadata: dict[str, Any] = {}             # escape hatch для данных форматов (col.gen и т.п.)

class EnumValue(BaseModel):
    name: str
    value: str | int | None = None   # None → подставляется name (на валидации)

class Enum(BaseModel):
    name: str
    description: str | None = None
    values: list[EnumValue] = []

class CustomType(BaseModel):
    name: str
    base: PRIMITIVE_TYPES | str      # str — валидация в composition/validator
    constraints: Constraints | None = None

class SourceModel(BaseModel):
    name: str
    description: str | None = None
    entities: list[Entity] = []
    enums: list[Enum] = []
    types: list[CustomType] = []
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(validate_assignment=True)
```

**Cached индексы.** `entity_map` / `enum_map` как `@property` пересобирают dict на каждый вызов (hotpath плагина). Вместо этого:

```python
class SourceModel(BaseModel):
    _entity_map: dict[str, Entity] = PrivateAttr(default={})
    _enum_map: dict[str, Enum] = PrivateAttr(default={})

    @model_validator(mode="after")
    def _build_maps(self) -> "SourceModel":
        self._entity_map = {e.name: e for e in self.entities}
        self._enum_map = {e.name: e for e in self.enums}
        return self

    def entity(self, name: str) -> Entity:     # KeyError с понятным сообщением
        ...
    def enum(self, name: str) -> Enum: ...
```

**Null-matrix.** Проверки §3.6 ТЗ — в Pydantic-валидаторе на уровне Entity (`mode="after"`), потому что комбинированное состояние по одному полю не видно:

| Комбинация | Откуда | Серьёзность |
|---|---|---|
| `required=false, nullable=false, default=None` | Field.model_validator | Error |
| `required=true, nullable=true` | validator.py | Warning (для future PATCH-семантики) |
| `required=true, default=None` при nullable=false | Field.model_validator | Error? |

> Согласуется с таблицей ТЗ §3.6: строго валидируются/ошибки — в Pydantic warnings — в `validator.py` (см. §4.4).

### 3.2 GeneratorConfig / GeneratorRules

```python
class InputSlice(BaseModel):
    entities: list[str] | None = None   # None/пусто = все
    enums: list[str] | None = None
    types: list[str] | None = None

class GeneratorConfig(BaseModel):
    id: str
    enabled: bool = True
    input: InputSlice = InputSlice()
    output_dir: Path
    on_conflict: Literal["overwrite", "skip", "error"] = "overwrite"
    cleanup: Literal["off", "prompt", "enabled"] = "prompt"
    options: dict[str, Any] = {}        # в т.ч. file_naming — зона плагина

class DefaultsConfig(BaseModel):
    naming_convention: NamingStyle | None = NamingStyle.SNAKE   # подсказка
    required_by_default: bool = False

class SourceConfig(BaseModel):
    path: Path
    input: InputSlice = InputSlice()

class GeneratorRules(BaseModel):
    version: str = "1.0"
    defaults: DefaultsConfig = DefaultsConfig()
    variables: dict[str, str] = {}
    sources: list[SourceConfig] = []
    generators: list[GeneratorConfig] = []
```

Генератор **не имеет `source`** — работает с составленным целым по срезу `input`. Срез = пересечение: `sources[].input` ∩ `generators[].input`.

Нейминг: `GeneratorRulesLoader` (не `BusinessConfigLoader`), файл `config/generator_rules.py`.

### 3.3 Преимущества Pydantic (с охватом v1.1)

| Возможность | Как |
|-------------|-----|
| Валидация null-matrix | `Field.model_validator(mode="after")` |
| Type-references | Literal + composition/validator |
| YAML → Model | `SourceModel.model_validate(yaml_data)` |
| Понятные ошибки | `e.errors()` → `ConfigValidationError` |
| Aliases | kebab-case не понадобится, т.к. у нас schema задокументирована как snake_case (только имена в header `format`, `version`; всё остальное snake_case) |
| Computed maps | `model_validator(mode="after")` + `PrivateAttr` |

### 3.4 Aliases (kebab-case)

ТЗ v1.1 — только snake_case ключи; поддержка kebab оставлена плагином формата (некоторые окружения ограничены). Ядро не даст "тихо" мержить разные регистры: `model_config = ConfigDict(extra="forbid")` — опечатки в ключах сразу в ошибке:

```python
class Field(BaseModel):
    ...
    model_config = ConfigDict(extra="forbid")   # защита от опечаток
```

---

## 4. Парсинг и композиция

### 4.1 Parser

```python
class Parser:
    def __init__(self, registry: FormatRegistry):
        self.registry = registry

    def parse_document(self, path: Path) -> RawDocument:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        fmt = data.get("format", "entity-model")     # неизвестный format → error
        version = data.get("version")                 # формат проверяет поддержку версии
        plugin = self.registry.get(fmt)
        return plugin.parse_yaml(data, base_path=path.parent)  # SourceModel
```

Реестр:

```python
class FormatRegistry:
    """Встроенный 'entity-model' + форматы от формат-плагинов."""
    def register(self, name: str, plugin: FormatPlugin) -> None: ...
    def get(self, name: str) -> FormatPlugin: ...   # UnknownFormatError
```

### 4.2 Imports (см. ADR-0001, полный алгоритм — там)

```python
class Composition:
    def __init__(self, parser: Parser): ...

    def resolve(self, path: Path) -> SourceModel:
        state = ResolveState(visiting=set(), imports={}, depth=0)
        doc = self._resolve_document(path, state)
        self._resolve_entity_extends(doc, state)
        return self._finalize(doc)

    def _resolve_document(self, path: Path, state) -> SourceModel:
        if path in state.visiting:
            raise CyclicImportError(state.full_cycle())
        if state.depth > MAX_IMPORT_DEPTH (10):
            raise ImportDepthError(path)
        state.visiting.add(path)
        doc = self.parser.parse_document(path)
        for imp in doc.model.imports:
            resolved = (imp.doc_root / imp.path).resolve()
            self._merge_or_register(doc, imp, resolved, state)
        state.visiting.remove(path)
        return doc

    def _merge_or_register(self, doc, imp, resolved, state):
        """YAML → merge (ADR-0001 #1–#5); прочее → imports-map под `as` (#6: дубль as → error)."""
```

### 4.3 Entity-level extends

```python
def merge_entity(parent: Entity, child: Entity) -> Entity:
    """ADR-0001 #3: parent-поля на своих позициях, override фиксирует позицию,
       новые поля child — в конце. Override — полное замещение атрибутов."""
    overridden = {f.name for f in child.fields} if child.fields else set()
    fields = [
        child.field(f.name) if f.name in overridden else f
        for f in parent.fields
    ]
    child_new = [f for f in child.fields if f.name not in overridden]
    ...
```

Порядок полей детерминирован и стабилен между запусками (важно для diff артефактов).

### 4.4 Validator (semantic, поверх Pydantic)

```python
class Diagnostic(BaseModel):
    level: Literal["warning", "error"]
    code: str                 # MG004 unknown-type, MG010 null-matrix, ...
    message: str
    location: str | None      # file:entity.field

def validate(model: SourceModel, config: GeneratorRules | None) -> list[Diagnostic]:
    ...
```

| Code | Проверка | Уровень |
|------|----------|---------|
| MG001 | Ссылка type на несуществующий enum/type | error |
| MG002 | Дубликат имени entity/enum/type после композиции | error |
| MG003 | Дубликат поля в entity | error |
| MG004 | Неизвестный тип | error |
| MG005 | Regex в `constraints.pattern` | error |
| MG006 | Циклический import / depth | error (в composition) |
| MG010 | Null-matrix запрещённые combo (§3.6 ТЗ) | error |
| MG011 | `required=true` + `nullable=true` | warning |
| MG012 | Entity.name не PascalCase | warning |
| MG013 | Неиспользуемый enum/type | warning |
| MG014 | `updated_at` устарела (entity.updated_at < file mtime) | warning |
| MG015 | Пустой description у required-поля | warning |

`--strict` повышает warnings до errors (уровень повышается, exit code 1).

Pydantic-валидаторы отвечают за структурные проверки; Validator — за семантику (cross-ref'ы).

---

## 5. Configuration Layer

### 5.1 AppConfig (pydantic-settings, v2-стиль)

```python
# metadata_generator/config/app_config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_destination: str = "stderr"       # stderr | stdout | file:./mg.log

    cache_dir: Path = Path(".mg-cache")
    config_file: Path | None = None       # путь к .mg.yaml (переопределяется -c)

    debug: bool = False
    verbose: bool = False
    quiet: bool = False
    watch_debounce_ms: int = 300
```

`plugins_dir` **удалена**: плагины из директорий с ручным `sys.path` не поддерживаются (§6.3). Дев-плагины — через editable install.

### 5.2 GeneratorRulesLoader

```python
class GeneratorRulesLoader:
    def load(self, path: Path) -> GeneratorRules:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            return GeneratorRules.model_validate(data)
        except ValidationError as e:
            raise ConfigValidationError.from_pydantic(e) from e

    @classmethod
    def discover(cls) -> GeneratorRules | None:
        """Ищет .mg.yaml от cwd вверх по дереву."""
```

### 5.3 Логирование (единая точка)

В проекте — **один** модуль логирования: `config/logging.py` (ранее дублировался `utils/logging.py` — убран).

```python
def setup_logging(config: AppConfig) -> None:
    handlers: list[logging.Handler] = []
    dest = config.log_destination.lower()
    if dest == "stdout":
        handlers.append(logging.StreamHandler(sys.stdout))
    elif dest.startswith("file:"):
        handlers.append(RotatingFileHandler(dest[5:], maxBytes=10 * 1024 * 1024, backupCount=5))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO),
                        format=config.log_format, handlers=handlers, force=True)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"mg.{name}")
```

> Console-вывод CLI результатов generate идёт не через logging: пользовательский вывод — rich; logging — для диагностики. Логи не попадают на stdout (не ломается `--format json`) — только stderr/file.

---

## 6. Plugin Loader

### 6.1 Entry points

```python
class PluginLoader:
    GROUP_GENERATORS = "metadata_generator.generators"
    GROUP_FORMATS    = "metadata_generator.formats"

    def load_generators(self) -> dict[str, GeneratorPlugin]:
        plugins = {}
        for ep in entry_points(group=self.GROUP_GENERATORS):
            cls = ep.load()                       # ImportError → DiagnosticError
            if cls.api_version != EXPECTED_API_VERSION:
                raise ApiVersionError(ep.name, cls.api_version, EXPECTED_API_VERSION)
            plugin = cls()
            if plugin.id != ep.name:
                logger.warning(...)   # предупреждение, но работает по plugin.id
            plugins[plugin.id] = plugin
        return plugins

    def load_formats(self) -> list[FormatPlugin]:
        ...
```

### 6.2 Регистрация (pyproject.toml проекта-плагина)

```toml
[project.entry-points."metadata_generator.generators"]
oracle-ddl = "my_oracle_generator:MyGenerator"

# для новых форматов:
[project.entry-points."metadata_generator.formats"]
sql-model = "my_oracle_generator.format:SqlModelFormat"
```

### 6.3 Локальная разработка плагина

`sys.path`-хаки и `plugins_dir` **не поддерживаются** (v1.1). Дев-цикл:

```bash
pip install -e ./plugins/my-generator   # editatable install
mg gen list                             # plugin виден
```

(Future, v0.3+: `--plugin path/to/module.py` — явный importlib spec loading, без правки sys.path.)

---

## 7. CLI (Typer)

### 7.1 Структура команд

```python
app = typer.Typer(name="mg", help="Metadata Generator", no_args_is_help=True)
app.add_typer(config_app, name="config")       # show, validate
app.add_typer(model_app,  name="model")        # validate
app.add_typer(gen_app,    name="gen")          # list

@app.command()
def generate(
    models: list[Path] = typer.Argument(None),
    generator: list[str] = typer.Option(None, "-g", "--generator"),
    config: Path      = typer.Option(None, "-c", "--config"),
    output: Path      = typer.Option(None, "-o", "--output"),
    var: list[str]    = typer.Option(None, "--var", help="KEY=VALUE, многократно"),
    dry_run: bool     = typer.Option(False, "--dry-run"),
    clean: bool       = typer.Option(False, "--clean", help="разовая зачистка илиphans"),
    strict: bool      = typer.Option(False, "--strict"),
    output_format: str = typer.Option("text", "--format"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    quiet: bool   = typer.Option(False, "-q", "--quiet"),
):
    """Генерация артефактов."""
    ...

@app.command()
def watch(models: list[Path] = typer.Argument(None)): ...

@app.command()
def init(): ...
```

### 7.2 Выходные коды и поведение при ошибках

| Ситуация | exit code |
|----------|-----------|
| Успех | 0 |
| Есть errors генерации (или warnings при --strict) | 1 |
| Config/usage: нет .mg.yaml, unknown generator id, --var без `=`, api_version mismatch | 2 |

Ошибка одного генератора: логируется, остальные продолжаются (aggregate отчёт в конце).

### 7.3 `--var`

```python
def parse_vars(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        if "=" not in item:
            raise UsageError(f"`--var` expects KEY=VALUE, got: {item}")   # exit 2
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out
```

Приоритет: CLI `--var` > `.mg.yaml variables`. Результат — `GenerationContext.variables`. Ядро не подставляет vars в пути/шаблоны сам — это решение плагина.

### 7.4 Formatters

```python
class OutputFormatter(ABC):
    @abstractmethod
    def format(self, report: EngineReport) -> str: ...

class TextFormatter(OutputFormatter): ...    # [✓] generator → dir/ tree
class JsonFormatter(OutputFormatter): ...    # {"success": ..., "artifacts": [...]}
```

`EngineReport` содержит общий результат (не путается с GenerationResult одного плагина).

---

## 8. Artifact Writer

### 8.1 Валидация путей

```python
def validate_artifact_path(output_dir: Path, artifact: Artifact) -> Path:
    path = (output_dir / artifact.path).resolve()
    output_resolved = output_dir.resolve()
    if not path.is_relative_to(output_resolved):
        raise ArtifactPathError(artifact, path)     # '..' / абсолютный / symlink
    return path
```

### 8.2 on_conflict

| `on_conflict` | Если файл существует |
|---|---|
| `overwrite` (default) | Перезаписать |
| `skip` | Не трогать (для ручной правки поверх сгенерированного) |
| `error` | Прервать генератор с ошибкой (артефакт + путь в сообщении) |

### 8.3 Atomicity

```python
_with_staging(output_dir):
    """Пишет во временный каталог (.mg-staging-XXXX), затем атомарно move в output_dir.
    При ошибке — staging удаляется; output_dir не остаётся в полуопределённом состоянии."""
```

### 8.4 Manifest и cleanup

После успешного **полного** запуска ядро пишет `output_dir/.mg-manifest.json`:

```json
{
  "mg_version": "0.1.0",
  "generated_at": "2026-11-10T12:34:56Z",
  "generator": "oracle-ddl",
  "artifacts": ["user.sql", "post.sql"]
}
```

**Cleanup** — сравнение файлов `output_dir` со списками из манифестов: файл, не описанный ни в одном манифесте, — осиротевший ("orphan"). Политика `cleanup: off | prompt | enabled` + разовый флаг `mg generate --clean`. Cleanup работает **только по манифестам** — никогда не удаляет файлы "по догадке", что защищает ручные файлы, лежащие рядом.

- `prompt` интерактивен; при `not sys.stdout.isatty()` → fallback `off` + warning.
- Манифест пишется только если весь запуск успеха (а не частичен).

---

## 9. Watch Mode

### 9.1 File Watcher (как в 1.0, lazy import)

```python
class Watcher:
    """watchdog Observer + DebounceHandler(debounce_ms).
    import watchdog — лениво, чтобы CLI не платил стартовой ценой пакета."""
```

### 9.2 Интерфейс для будущего кэширования

```python
class CacheStrategy(ABC):
    @abstractmethod
    def get_hash(self, path: Path) -> str: ...
    @abstractmethod
    def is_changed(self, path: Path) -> bool: ...
    @abstractmethod
    def get_dependencies(self, path: Path) -> list[Path]: ...
```

---

## 10. Структура проекта (код)

```
metadata-generator/
├── src/metadata_generator/
│   ├── __init__.py                  # публичный API (см. §2)
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                  # typer app (генерация, watch, init) + sub-apps
│   │   ├── config_cmds.py           # mg config show/validate
│   │   ├── model_cmds.py            # mg model validate
│   │   ├── gen_cmds.py              # mg gen list
│   │   └── formatters.py            # TextFormatter, JsonFormatter
│   ├── core/
│   │   ├── __init__.py
│   │   ├── model.py                 # SourceModel, Entity, Field, Constraints, ...
│   │   ├── parser.py                # Parser, RawDocument
│   │   ├── composition.py           # imports/extends, merge (ADR-0001)
│   │   ├── validator.py             # semantic валидация (Diagnostic)
│   │   └── naming.py                # NamingStyle, transform()
│   ├── config/
│   │   ├── __init__.py
│   │   ├── app_config.py            # AppConfig
│   │   ├── generator_rules.py       # GeneratorRules, GeneratorRulesLoader
│   │   └── logging.py               # setup_logging(), get_logger() — ЕДИНСТВЕННАЯ точка
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── engine.py                # Engine orchestration
│   │   ├── plugin_loader.py         # PluginLoader (generators + formats)
│   │   ├── format_registry.py       # FormatRegistry
│   │   └── artifact_writer.py       # ArtifactWriter (validate paths, on_conflict, atomic, manifest)
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── generator.py             # GeneratorPlugin, GeneratorInput, GenerationContext, Artifact
│   │   └── formats.py               # FormatPlugin
│   ├── watch/
│   │   ├── __init__.py
│   │   ├── watcher.py               # Watcher (lazy watchdog), DebounceHandler
│   │   └── cache.py                 # CacheStrategy (future)
│   └── utils/
│       ├── __init__.py
│       └── exceptions.py            # ConfigValidationError, CyclicImportError, ...
├── tests/
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_composition.py      # каждый пункт ADR-0001
│   │   ├── test_validator.py
│   │   ├── test_config.py
│   │   └── test_naming.py
│   ├── property/
│   │   └── test_parser.py           # hypothesis: не падает на мусоре; round-trip
│   ├── integration/
│   │   └── test_generate.py
│   ├── golden/
│   │   ├── fixtures/models/         # входные модели
│   │   ├── fixtures/expected/       # ожидаемые артефакты
│   │   └── test_golden.py           # diff-based regression
│   └── conftest.py
├── docs/
│   ├── requirements/                # ТЗ (index, v1.0, v1.1)
│   ├── system-design/
│   └── adr/                         # 0001-composition-merge-semantics.md
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 11. Тестирование (охват в 1.1)

### 11.1 Priorities

1. **Golden-file**: fixtures → expected artifacts (главная защита от регрессии артефактов).
2. Merge-семантика ADR-0001 — тест на каждое правило (1–12 из таблицы решений).
3. **Null-matrix** — 4 валидных состояния + запрещённые combos с кодом.
4. Parser: simple / imports / entity.extends / cycle / depth / unknown format / unknown version.
5. Integration CLI: полный цикл, exit codes, --strict, --var, --dry-run.

### 11.2 Property-based (перезаписана формулировка)

```python
@given(st.dictionaries(keys, values))       # ЛЮБОЙ dict
def test_never_crashes_on_arbitrary_input(data):
    """Parser на произвольном dict не падает (только PyYAML/pydantic ошибки)."""
    with pytest.raises((ValidationError, ConfigError)) if invalid else None: ...

@given(valid_model_data())                   # стратегия строит валидные модели
def test_round_trip(data) -> None:
    model = SourceModel.model_validate(data)
    assert SourceModel.model_validate(model.model_dump()) == model
```

Стратегия валидных данных — комбинирует: email → entity names/fields/types/enums/constraints (правила null-matrix учитываются).

---

## 12. Зависимости (pyproject.toml)

```toml
[project]
name = "metadata-generator"
version = "0.1.0"
description = "CLI tool for metadata-driven code generation"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "pyyaml>=6.0.1",
    "rich>=13.7.0",
    "watchdog>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.100.0",
    "ruff>=0.4.0",
    "mypy>=1.8.0",
]

[project.scripts]
mg = "metadata_generator.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

> `watchdog` — lazy-import в `watch/watcher.py`; CLI без `mg watch` не платит стартовой ценой.
> v1.0 не включает встроенных генераторов и, соответственно, `[project.entry-points]` — entry points регистрируют архивные плагины.

---

## 13. Проектировочные решения (v1.1, сводка)

| Решение | Причина | Где |
|---------|---------|-----|
| Заголовок документа: только `format` + `version` | Наследование формата — зона формат-плагина; нет двойного extends | ТЗ §3.4 |
| Сущности изолированы (без relations в базе) | Нейтральность ядра | ТЗ §1 |
| Два типа плагинов (generators, formats) | Реестр форматов расширяем | §6 |
| Вход генератора — цельная срезанная модель | Cross-entity артефакты (barrel, миграции) | ТЗ §6.1 |
| App-related плагину не передаётся | Чистый публичный контракт | §2.1 |
| Имена файлов задаёт плагин, ядро валидирует пути | Нет двух источников имен | §8.1 |
| `naming_convention` — подсказка в context | Не переименовывать модель молча | §2.6 |
| Плагин `api_version` | Обратная совместимость контракта | §6.1 |
| Atomic write + manifest cleanup | Безопасная запись и зачистка | §8 |
| Локальные плагины через pip -e, не sys.path | Стандарт, без хаков | §6.3 |
| Логи в stderr/file, CLI-вывод в stdout (rich) | Совместимость с `--format json` | §5.3 |
