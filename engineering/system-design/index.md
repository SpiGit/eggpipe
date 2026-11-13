# System Design — Eggpipe

> Документ реализации для проекта eggpipe. Соответствует [ТЗ v2.2](../requirements/v2.2.md). Правила композиции — [ADR-0001](../adr/0001-composition-merge-semantics.md), [ADR-0007](../adr/0007-format-inheritance.md), [ADR-0008](../adr/0008-model-units-and-source-layouts.md).

*Версия документа: 2.2. Дата: 2026-11-13.*

---

## 1. Обзор архитектуры

### 1.1 Компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│                      eggpipe (ядро)                   │
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
| **Config** | AppConfig (CLI → env → .env → defaults) + ProjectConfig (.eggpipe.yaml) |
| **Engine** | Оркестрация: парсинг → composition → validate → generate → write |
| **FormatRegistry** | Реестр форматов: встроенный `entity-model` + форматы от формат-плагинов |
| **Parser** | YAML parse, imports, entity.extends |
| **Composition** | Merge по правилам ADR-0001 |
| **Validator** | Кросс-сущностные проверки: warnings + errors (null-matrix, дубликаты, unused, stale dates) |
| **Plugin Loader** | Ленивая загрузка плагинов из entry points, проверка `api_version` |
| **Planning** | План create/update/skip/delete, ownership и конфликты до записи |
| **Lock** | `.eggpipe/lock` — защита от параллельной записи в один `output_dir` |
| **Artifact Writer** | Проверка путей, on_conflict, atomic write, global manifest, cleanup |
| **Plugins** | Генераторы (и формат-плагины) — код + шаблоны |

### 1.2 Поток данных

```
1. CLI получает команду
        │
2. AppConfig создаётся (CLI → env → .env → defaults)
        │
3. ProjectConfigLoader загружает .eggpipe.yaml
        │
4. Для каждого source:
    ├── Discovery: layout (monolith/file-per-model/directory-per-model)
    ├── FormatRegistry выбирает формат каждого файла-слоя
    ├── Parser парсит YAML → layer document (imports/extends — ADR-0001)
    ├── layer_entity валидирует слой
    ├── слои одной модели мержатся по ADR-0008
    └── full_entity валидирует итоговую сущность
        │
5. Composition собирает SourceModel из sources (union),
   валидирует глобальные инварианты (дубликаты имён между source)
        │
6. Plugin Loader загружает выбранные генераторы (lazy, api_version)
        │
7. Для каждого генератора:
    ├── Engine вычисляет срез + closure → ModelSlice
    ├── проверка Entity.format против input_formats (EG033)
    ├── validate_config() → Diagnostic[]
    ├── формирует GeneratorInput (model, context, config)
    ├── Plugin.generate() → GenerationResult
    ├── Planning: ownership, конфликты, on_conflict
    └── Lock → ArtifactWriter пишет артефакты (atomic, manifest)
        │
8. CLI выводит EngineReport (text / json), exit code по §8.4 ТЗ
```

---

## 2. Интерфейсы плагинов

> Публичный API ядра экспортирует **только** эти контракты (из `eggpipe.__init__`): `GeneratorPlugin, GeneratorInput, GenerationResult, Artifact, GenerationContext, FormatInfo, FormatSchema, ImportedFile, SourceModel, ModelSlice, Entity, EntityIdentity, FieldIdentity, FieldDef, EnumDef, CustomType, GeneratorConfig, NamingStyle, transform, Diagnostic, EngineReport, Engine, AppConfig, ProjectConfig, ProjectConfigLoader, FormatRegistry, FormatPlugin, EntityModelFormat, MergePolicy, generator, Provenance, git_provenance, UNSET, PRIMITIVE_TYPES, Constraints` и базовые исключения. Всё остальное — внутреннее и может меняться. Пакет поставляет `py.typed`.

### 2.1 GeneratorInput — вход генератора

```python
class GeneratorInput(BaseModel):
    """Immutable входные данные генератора."""
    model: ModelSlice            # замкнутый срез: entities/enums/types
    config: GeneratorConfig      # свой блок из .eggpipe.yaml (id, options, output_dir, ...)
    context: GenerationContext   # variables, formats, imports, source paths

    model_config = ConfigDict(frozen=True)
```

**AppConfig в плагин не передаётся** — технические настройки вне клиентского контракта.

### 2.2 GenerationContext

```python
class GenerationContext(BaseModel):
    """Контекст генерации; копируется на каждый генератор."""
    variables: Mapping[str, str]         # --var ∪ .eggpipe.yaml (CLI > config), read-only
    naming_hint: NamingStyle | None     # defaults.naming_convention (подсказка!)
    imports: Mapping[str, ImportedFile] # alias (as) → файл, read-only
    sources: tuple[Path, ...]           # относительные пути source-файлов (провенанс)
    formats: frozenset[FormatInfo]      # форматы среза
    run_id: str                         # идентификатор запуска
    config_dir: Path                    # каталог .eggpipe.yaml

    model_config = ConfigDict(frozen=True)

@dataclass(frozen=True)
class FormatInfo:
    name: str
    version: str

class ImportedFile(BaseModel):
    name: str          # значение `as` из imports
    path: Path         # относительный путь для артефактов
    content: bytes     # ядро читает; decode — задача плагина

    def text(self, encoding: str = "utf-8") -> str: ...
```

### 2.3 Artifact и GenerationResult — выход генератора

```python
class Artifact(BaseModel):
    """Один сгенерированный файл."""
    path: str                    # ОТНОСИТЕЛЬНЫЙ POSIX-путь; плагин сам решает имя
    content: str                 # текст; UTF-8, LF, без BOM

class GenerationResult(BaseModel):
    artifacts: list[Artifact] = []
    warnings: list[Diagnostic] = []
    errors: list[Diagnostic] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
```

Правила:

- Если `errors` непустой — артефакты **отбрасываются**.
- `warnings`/`errors` — структурированные диагностики с кодом и локацией.
- Binary-артефакты — не-цель v1; `content` только `str`.

### 2.4 GeneratorPlugin

**Основной API — декоратор `@generator`:**

```python
@generator(id="tpch", input_formats={"entity-model"})
def tpch(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    ...
```

- декоратор создаёт класс-адаптер `GeneratorPlugin` и регистрирует его;
- аргументы инжектятся по аннотациям: `ModelSlice`, `GenerationContext`, `GeneratorConfig`;
- возврат нормализуется: `GenerationResult`, `Artifact`, `list[Artifact]`, `tuple[Artifact, ...]`;
- сигнатура проверяется при загрузке плагина;
- классовый API ниже остаётся advanced-вариантом.

```python
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

API_VERSION = Literal["1"]

class GeneratorPlugin(ABC):
    api_version: ClassVar[Literal["1"]]   # ядро проверяет при загрузке
    id: ClassVar[str]                     # совпадает с entry point id
    name: ClassVar[str] = ""              # default → id
    input_formats: ClassVar[set[str] | None]
                                          # обязателен: None = любой; set = форматы и наследники

    @abstractmethod
    def generate(self, input: GeneratorInput) -> GenerationResult: ...

    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        return []                         # semantic-ошибки конфига генератора
```

**Совместимость форматов:** ядро проверяет каждую сущность среза против `input_formats`
с учётом цепочки `extends`; несовместимость — EG033 до вызова `generate()`.
Это pre-flight ошибка всего запуска: артефакты не пишутся, `--plan`/`--check` падают, exit 2.
`GenerationContext.formats` содержит форматы среза; `Entity.format` — источник истины.

**Жизненный цикл:** `__init__` → `validate_config()` → `generate()`.

- Ошибки `validate_config()` — ошибки выбранного генератора; остальные генераторы продолжают работу.
- Исключение из любого метода ловится ядром и превращается в `Diagnostic` с traceback в debug-логах; exit 1.
- Экземпляр создаётся один раз на запуск; потокобезопасность не требуется (v0.1–v0.2 — однопоточно).
- Плагин не пишет файлы сам и не мутирует вход.

### 2.5 FormatPlugin

```python
class FormatPlugin(ABC):
    """Контракт формата: минимальный интерфейс для FormatRegistry."""
    api_version: ClassVar[Literal["1"]]
    format_names: ClassVar[list[str]]          # ["sql-model", ...]
    supported_versions: ClassVar[list[str]]    # упорядоченный; последняя = latest
    extends: ClassVar[str | None] = None       # базовый формат
    base_versions: ClassVar[dict[str, str]] = {}  # B version -> A version
    primitive_types: ClassVar[set[str]]        # примитивы формата
    schemas: ClassVar[dict[str, FormatSchema]] # version -> layer/full entity

    @abstractmethod
    def parse(self, raw: dict, base_path: Path) -> ModelDocument: ...

    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        return []
```

`EntityModelFormat` — конкретная база ядра для форматов, которые **расширяют** entity-model:

```python
class EntityModelFormat(FormatPlugin):
    """Реализует базовую схему entity-model; наследники добавляют расширения."""
    format_names = ["entity-model"]
    supported_versions = ["1.0"]
    primitive_types = PRIMITIVE_TYPES
    schemas = {"1.0": FormatSchema(layer_entity=LayerEntity, full_entity=Entity)}

    def parse(self, raw: dict, base_path: Path) -> ModelDocument:
        document = build_entity_model_document(raw, base_path)  # header + схема
        self.parse_extensions(document, raw)                     # hook
        return document

    def parse_extensions(self, document: ModelDocument, raw: dict) -> None:
        """Наследник добавляет поля/metadata; база ничего не делает."""

    def validate(self, document: ModelDocument) -> list[Diagnostic]:
        diagnostics = validate_entity_model(document)
        return diagnostics + self.validate_extensions(document)

    def validate_extensions(self, document: ModelDocument) -> list[Diagnostic]:
        return []
```

- `extends` — одиночное наследование; цикл/глубина > 10 — EG034.
- `B extends A` — B надмножество A; переименование/удаление полей A запрещено.
- Версии независимы: `base_versions[B_version] = A_version`.
- Версия в документе опциональна; нет версии — последняя из `supported_versions`.
- `schemas[version].full_entity` должен наследовать базовую `full_entity`; иначе EG034.
- `primitive_types` B — надмножество A; иначе EG034.
- Расширение может задать свои Pydantic-модели: `BModel(AModel)`.
- `layer_entity` валидирует один файл-слой, `full_entity` — итог после merge.
- `EntityIdentity` / `FieldIdentity` дают дельта-моделям только identity-поля (`name`).
- Обязательность новых полей определяет формат: `layer_entity` может быть partial, `full_entity` — complete.
- Документ остаётся общим конвертом; first-class document-level поля — future, в v2.2 через `metadata`.
- `entity-model` зарезервирован; попытка переопределить — Error при регистрации.
- Дополнительные поля могут быть first-class полями модели; `metadata` остаётся extension point.
- Формат и версия передаются через `Entity.format` / `Entity.format_version`;
  сводка — `GenerationContext.formats`.
- Формат задаётся только файлами модели; `.eggpipe.yaml` его не задаёт.

### 2.6 NamingStyle

```python
class NamingStyle(StrEnum):
    SNAKE = "snake_case"
    CAMEL = "camelCase"
    PASCAL = "pascal_case"
    KEBAB = "kebab-case"

def transform(name: str, style: NamingStyle) -> str: ...
```

- `defaults.naming_convention` из `.eggpipe.yaml` — **подсказка**: ядро кладёт её в `context.naming_hint` и никогда не переименовывает канонические имена (Entity.name остаётся как в YAML).
- Если `naming_convention` не задан, `naming_hint = None` (а не неявный SNAKE).
- Какую трансформацию куда применить — решает плагин (SQL table → snake, Pydantic class → pascal и т.п.).
- `transform` обязан быть детерминированным, сохранять цифры и корректно обрабатывать акронимы (`HTTPServer` → `http_server`/`HttpServer`); edge-cases покрываются тестами.

### 2.7 Пример генератора

```python
# my-generator/src/my_generator/__init__.py
from eggpipe import (
    GeneratorPlugin, GeneratorInput, GenerationResult, Artifact,
    NamingStyle, transform,
)

class MyGenerator(GeneratorPlugin):
    api_version = "1"
    id = "my-generator"
    name = "My Generator"
    input_formats = {"entity-model"}

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

### 2.8 Engine — библиотечный фасад

```python
class Engine:
    def __init__(
        self,
        config: AppConfig,
        rules: ProjectConfig,
        *,
        config_dir: Path | None = None,
        generators: Mapping[str, GeneratorPlugin] | None = None,
        formats: FormatRegistry | None = None,
        source_paths: list[Path] | None = None,
        variables: Mapping[str, str] | None = None,
    ): ...

    def build(self) -> EngineReport: ...      # парсинг/валидация/генерация без записи
    def generate(self) -> EngineReport: ...   # build + запись артефактов
    def check(self) -> EngineReport: ...      # drift без записи; success=false, exit_code=1
```

- `Engine` не вызывает `sys.exit` и не настраивает root-logger.
- Реестры можно инжектировать — для тестов, библиотечного встраивания и reference-плагина.
- `config_dir` задаёт базу для относительных путей; `source_paths`/`variables` — явные override'ы.
- `EngineReport` содержит `success`, `run_id`, `diagnostics`, `generators[]`, `artifacts[]`, `timings`, `exit_code`.
- Config/usage-ошибки бросаются исключениями; ошибки парсинга и генерации агрегируются в отчёт.

---

## 3. Внутренние модели ядра (Pydantic v2)

### 3.1 Document / SourceModel / ModelSlice

```python
PRIMITIVE_TYPES = frozenset({
    "string", "text", "integer", "bigint", "boolean",
    "float", "date", "datetime", "uuid", "json",
})   # набор встроенного entity-model; format-плагин объявляет свой

class _Unset:
    def __repr__(self) -> str: return "UNSET"

UNSET = _Unset()   # отличает «default не задан» от default=None

class Constraints(BaseModel):
    min: int | float | date | datetime | None = None
    max: int | float | date | datetime | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    model_config = ConfigDict(extra="forbid", frozen=True)

class FieldDef(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: str
    description: str | None = None
    required: bool = False
    nullable: bool = False
    default: str | int | float | bool | date | datetime | None | _Unset = UNSET
    constraints: Constraints | None = None
    metadata: dict[str, Any] = {}
    source: Path | None = Field(default=None, exclude=True, repr=False)
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_serializer("default")
    def _serialize_default(self, value, _info): ...

    @model_serializer(mode="wrap")
    def _serialize(self, handler): ...  # опускает ключ default при UNSET

class ExtendsRef(BaseModel):
    import_: str = Field(alias="import")
    entity: str
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

class Entity(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    version: str | int | None = None
    updated_at: date | datetime | None = None
    extends: str | ExtendsRef | None = None
    fields: tuple[FieldDef, ...] = ()
    metadata: dict[str, Any] = {}
    format: str | None = Field(default=None, exclude=True, repr=False)
    format_version: str | None = Field(default=None, exclude=True, repr=False)
    source: Path | None = Field(default=None, exclude=True, repr=False)
    layer_sources: tuple[Path, ...] = Field(default=(), exclude=True, repr=False)
    model_config = ConfigDict(extra="forbid", frozen=True)

class EnumValue(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str | int | None = None
    description: str | None = None
    model_config = ConfigDict(extra="forbid", frozen=True)

class EnumDef(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    values: tuple[EnumValue, ...] = ()
    metadata: dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)

class CustomType(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    base: str
    constraints: Constraints | None = None
    metadata: dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)

class _IndexedModel(BaseModel):
    """Immutable модель с кэшированными индексами."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    _entity_map: dict[str, Entity] = PrivateAttr(default_factory=dict)
    _enum_map: dict[str, EnumDef] = PrivateAttr(default_factory=dict)
    _type_map: dict[str, CustomType] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _build_maps(self):
        object.__setattr__(self, "_entity_map", {e.name: e for e in self.entities})
        object.__setattr__(self, "_enum_map", {e.name: e for e in self.enums})
        object.__setattr__(self, "_type_map", {t.name: t for t in self.types})
        return self

    def entity(self, name: str) -> Entity: ...
    def enum(self, name: str) -> EnumDef: ...
    def type(self, name: str) -> CustomType: ...
    def resolve_type(self, field: FieldDef) -> Entity | EnumDef | CustomType | str: ...

class ModelSlice(_IndexedModel):
    entities: tuple[Entity, ...] = ()
    enums: tuple[EnumDef, ...] = ()
    types: tuple[CustomType, ...] = ()

class SourceModel(ModelSlice):
    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = {}

class ImportSpec(BaseModel):
    path: str
    alias: str | None = None
    kind: Literal["yaml", "resource"]
    model_config = ConfigDict(extra="forbid", frozen=True)

class ModelDocument(BaseModel):
    format: str
    version: str
    path: Path
    imports: tuple[ImportSpec, ...] = ()
    model: SourceModel
    metadata: dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)
```

**Индексы.** Карты строятся один раз после создания immutable-модели; мутации и `validate_assignment` исключены. Дубликаты имён проверяются в `validator.py` по спискам (до использования карт), чтобы словарь не «схлопнул» конфликт.

**Сериализация `UNSET`.** `FieldDef` с `UNSET` не выводит ключ `default` в `model_dump()`; явный
`default: null` выводится как `null`. Это нужно для round-trip и JSON Schema.

**Null-matrix.** Все проверки — в `validator.py` (не в Pydantic), потому что нужны код, локация и уровень:

| Условие | Код | Уровень |
|---|---|---|
| `nullable=false` и `default is None` (ключ задан явно) | EG010 | Error |
| `required=true` и `nullable=true` | EG011 | Warning |
| `default is not UNSET` и тип не совпадает с итоговым `type` | EG016 | Error |
| `default` нарушает constraints/enum | EG017 | Error |

`default is UNSET` — валидное состояние для `required=false`, `nullable=false`: допустимость отсутствия значения определяет формат/генератор. Комбинация не является ошибкой ядра.

### 3.2 GeneratorConfig / ProjectConfig

```python
class InputSelection(BaseModel):
    entities: tuple[str, ...] | None = None   # None/пусто = все
    enums: tuple[str, ...] | None = None
    types: tuple[str, ...] | None = None
    model_config = ConfigDict(extra="forbid", frozen=True)

class GeneratorConfig(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    enabled: bool = True
    input: InputSelection = InputSelection()
    output_dir: Path                    # относительный путь
    on_conflict: Literal["overwrite", "skip", "error"] = "overwrite"
    cleanup: Literal["off", "prompt", "enabled"] = "off"
    options: dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)

class DefaultsConfig(BaseModel):
    naming_convention: NamingStyle | None = None   # подсказка; None = не задана
    model_config = ConfigDict(extra="forbid", frozen=True)

class ResourceSpec(BaseModel):
    path: str
    as_: str | None = Field(default=None, alias="as")
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

class SourceConfig(BaseModel):
    path: Path
    layout: Literal["monolith", "file-per-model", "directory-per-model"]
    model_dirs: tuple[str, ...] | None = None       # glob/точный список (directory)
    files: tuple[str, ...] | None = None            # glob/точный список
    models: dict[str, ModelOverride] = {}           # override для каталога
    input: InputSelection = InputSelection()
    model_config = ConfigDict(extra="forbid", frozen=True)

class ModelOverride(BaseModel):
    files: tuple[str, ...] | None = None
    resources: tuple[ResourceSpec, ...] = ()
    model_config = ConfigDict(extra="forbid", frozen=True)

class DiagnosticsConfig(BaseModel):
    stale_dates: bool = False              # EG014 opt-in
    ignore: frozenset[str] = frozenset()   # коды EG...
    model_config = ConfigDict(extra="forbid", frozen=True)

class ProjectConfig(BaseModel):
    version: Literal["1.0"]              # обязательна
    defaults: DefaultsConfig = DefaultsConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    variables: dict[str, str] = {}
    resources: tuple[ResourceSpec, ...] = ()
    sources: tuple[SourceConfig, ...] = ()
    generators: tuple[GeneratorConfig, ...] = ()
    model_config = ConfigDict(extra="forbid", frozen=True)
```

Генератор **не имеет `source`** — работает с составленным целым. `sources[].input` фильтрует содержимое своего source; итоговая модель — union отфильтрованных источников. Срез генератора = `generators[].input` по этой модели + closure.

`output_dir` обязан быть относительным (абсолютный → EG3xx, exit 2); `-o` заменяет базу, относительные пути резолвятся от `config_dir`.

Нейминг: `ProjectConfigLoader` (не `BusinessConfigLoader`), файл `config/project_config.py`.

### 3.3 Преимущества Pydantic (с охватом v1.3)

| Возможность | Как |
|-------------|-----|
| Структурная валидация | `model_validate`, `extra="forbid"`, pattern |
| Различение `UNSET`/`null` | sentinel + `model_fields_set` |
| Type-references | строки + `validator.py` |
| YAML → Model | `ModelDocument.model_validate(...)` |
| Понятные ошибки | `e.errors()` → `ConfigValidationError` (EG3xx) |
| Computed maps | immutable `PrivateAttr` + `model_validator(mode="after")` |
| Сериализация | `model_dump(mode="json")`, JSON Schema |

Pydantic отвечает только за структуру. Null-matrix, ссылочная целостность и ограничения — `validator.py`, чтобы иметь коды и уровни.

### 3.4 Aliases

- Публичная YAML-схема — только `snake_case`. Исключение — ключ `import` в `ExtendsRef`, для него задан alias.
- `extra="forbid"` включён на всех моделях: опечатки сразу дают ошибку.
- Format-плагин может добавить собственные aliases/metadata, но не менять базовые ключи.
- Kebab-case в базовой схеме не поддерживается; это зона format-плагина.

---

## 4. Парсинг и композиция

### 4.1 Parser

```python
class Parser:
    def __init__(self, registry: FormatRegistry):
        self.registry = registry

    def parse_document(self, path: Path) -> ModelDocument:
        data = load_yaml(path)              # ruamel.yaml safe, YAML 1.2
        if not isinstance(data, dict):
            raise DocumentError(EG000, path, "document root must be a mapping")
        fmt = data.get("format")
        if not fmt:
            raise DocumentError(EG007, path, "`format` is required")
        plugin = self.registry.get(fmt)      # UnknownFormatError → EG007
        version = normalize_version(data.get("version"))   # 1.0 → "1.0"
        if version is None:
            version = plugin.supported_versions[-1]        # latest
        if version not in plugin.supported_versions:
            raise DocumentError(EG008, path, f"{fmt} does not support {version}")
        document = plugin.parse(data, base_path=path.parent)
        return document
```

YAML-загрузчик:

- `ruamel.yaml` в safe-режиме (YAML 1.2).
- `allow_duplicate_keys=False` → EG000.
- multi-document (`---`) → EG000.
- не-dict корень → EG000.
- `version` принимает строку или число и нормализуется; иначе EG008.
- абсолютные пути импортов запрещены; см. §4.2.

Реестр:

```python
@dataclass(frozen=True)
class FormatRegistryInfo:
    name: str
    versions: tuple[str, ...]
    primitive_types: frozenset[str]

class FormatRegistry:
    """Встроенный 'entity-model' + форматы от формат-плагинов."""
    def register(self, plugin: FormatPlugin) -> None:
        # duplicate name → FormatConflictError (EG007)
        # name == "entity-model" для внешнего плагина → EG007
        # неверное наследование/схемы/примитивы → FormatInheritanceError (EG034)
    def get(self, name: str) -> FormatPlugin: ...   # UnknownFormatError
    def list(self) -> list[FormatRegistryInfo]: ...
    def validate(self) -> None: ...                 # проверка цепочки extends
```

### 4.2 Imports (см. ADR-0001, полный алгоритм — там)

```python
@dataclass
class ResolveState:
    project_root: Path
    allow_outside: bool
    cache: dict[Path, ModelDocument]      # resolved path → document
    visiting: list[Path]                  # stack для цикла
    resources: dict[str, ImportedFile]
    depth: int = 0

class Composition:
    def __init__(self, parser: Parser): ...

    def resolve(self, path: Path, state: ResolveState) -> SourceModel:
        document = self._resolve_document(path, state)
        self._resolve_extends(document, state)
        return self._finalize(document, state)

    def _resolve_document(self, path: Path, state: ResolveState) -> ModelDocument:
        canonical = canonical_path(path)          # resolve + realpath
        if canonical in state.visiting:
            raise CyclicImportError(state.cycle(canonical))       # EG006
        if state.depth > MAX_IMPORT_DEPTH:
            raise ImportDepthError(canonical)                     # EG006
        if canonical in state.cache:              # один документ — один раз
            return state.cache[canonical]

        state.visiting.append(canonical)
        state.depth += 1
        try:
            document = self.parser.parse_document(canonical)
            for spec in document.imports:
                resolved = resolve_import(canonical.parent, spec, state)  # EG022
                if spec.kind == "yaml":
                    imported = self._resolve_document(resolved, state)
                    document = merge_documents(document, imported, spec)  # EG002
                else:
                    state.resources[spec.alias] = read_resource(resolved, spec)
            state.cache[canonical] = document
            return document
        finally:
            state.visiting.pop()
            state.depth -= 1
```

- `resolve_import` разрешает путь относительно **файла, где объявлен импорт**, и проверяет project root (EG022).
- `merge_documents` реализует ADR-0001 #1–#5 с уточнениями ADR-0008: entities/enums/types объединяются, дубликаты имён → EG002; `model.name/description` импорта не мержатся, `metadata` мержится аддитивно.
- Ресурсы (`kind="resource"`) читаются как bytes и складываются в `state.resources`; дубль alias → EG025.
- Один resolved-path обрабатывается один раз; повторный импорт/источник не дублирует сущности (EG024 — Warning).
- `state.resources` попадает в `GenerationContext.imports`.

### 4.3 Entity-level extends

```python
def merge_entity(parent: Entity, child: Entity) -> Entity:
    """ADR-0001 #2–#3 + ADR-0008: наследуются поля и атрибуты, metadata мержится."""
    if len({f.name for f in child.fields}) != len(child.fields):
        raise DuplicateFieldError(child.name)                    # EG003
    overrides = {f.name: f for f in child.fields}
    fields = tuple(overrides.pop(f.name, f) for f in parent.fields)
    fields += tuple(f for f in child.fields if f.name in overrides)
    updates = {"fields": fields, "extends": None,
               "metadata": deep_merge(parent.metadata, child.metadata)}
    for name in ("description", "version", "updated_at"):
        if getattr(child, name) is None:
            updates[name] = getattr(parent, name)
    return child.model_copy(update=updates)
```

Разрешение `extends`:

```python
def resolve_extends(entity: Entity, scope: ImportScope, stack: tuple[str, ...]) -> Entity:
    if entity.extends is None:
        return entity
    if entity.name in stack:
        raise ExtendsCycleError(stack + (entity.name,))           # EG009
    if len(stack) > MAX_EXTENDS_DEPTH:
        raise ExtendsDepthError(entity.name)                       # EG009
    parent = scope.resolve(entity.extends)   # short name или {import, entity}; EG009
    parent = resolve_extends(parent, scope, stack + (entity.name,))
    return merge_entity(parent, entity)
```

- `ImportScope` — индекс entity по alias и по имени в import-closure документа.
- Короткое имя допустимо только при уникальном совпадении; иначе EG009.
- `extends` разрешается только внутри closure своего документа; сущность из другого source — EG009.
- Наследуются `description`, `version`, `updated_at`, `metadata` и `fields`; child переопределяет scalar-атрибуты, metadata мержится аддитивно.
- Порядок полей детерминирован.

### 4.4 Validator (semantic, поверх Pydantic)

```python
class DiagnosticLocation(BaseModel):
    file: Path | None = None
    entity: str | None = None
    field: str | None = None
    path: str | None = None          # JSON-path внутри документа
    format: str | None = None
    version: str | None = None
    generator: str | None = None
    artifact: str | None = None

class Diagnostic(BaseModel):
    level: Literal["warning", "error"]
    code: str                        # EG...
    message: str
    location: DiagnosticLocation | None = None

def validate(
    model: SourceModel,
    rules: ProjectConfig,
    *,
    project_root: Path,
    format_plugin: FormatPlugin,
) -> list[Diagnostic]: ...
```

| Code | Проверка | Уровень | Фаза |
|------|----------|---------|------|
| EG000 | YAML syntax / duplicate keys / multi-doc / non-dict | error | parse |
| EG001 | Ссылка type на несуществующий enum/type | error | validate |
| EG002 | Дубликат имени entity/enum/type после композиции | error | composition |
| EG003 | Дубликат поля в entity | error | validate |
| EG004 | Неизвестный тип (не primitive формата, не enum/type) | error | validate |
| EG005 | Некорректный regex в `constraints.pattern` | error | validate |
| EG006 | Циклический import / depth > 10 | error | composition |
| EG007 | `format` отсутствует / неизвестен | error | parse |
| EG008 | `version` не поддерживается | error | parse |
| EG009 | `extends` не найден / неоднозначен / цикл / depth > 10 | error | composition |
| EG010 | `nullable=false` + `default=null` | error | validate |
| EG011 | `required=true` + `nullable=true` | warning | validate |
| EG012 | Entity.name не PascalCase | warning | validate |
| EG013 | Неиспользуемый enum/type | warning | validate |
| EG014 | `updated_at` устарела (file-per-model, opt-in) | warning | validate |
| EG015 | Пустой description у required-поля | warning | validate |
| EG016 | `default` не приводится к итоговому type | error | validate |
| EG017 | `default` нарушает constraints/enum | error | validate |
| EG018 | Неизвестное имя в `input` | error | slice |
| EG019 | Пустой enum / дубликат имени/значения | error | validate |
| EG020 | Цикл `CustomType.base` / depth > 10 | error | validate |
| EG021 | Неприменимый/противоречивый constraint | error | validate |
| EG022 | Импорт вне project root | error | composition |
| EG023 | YAML в `sources` не является документом модели | error | discovery |
| EG024 | Дубликат resolved-пути | warning | discovery |
| EG025 | Дубликат alias `as` | error | composition |
| EG026 | Case-insensitive коллизия имён | warning | validate |
| EG027 | Пустой каталог модели | warning | discovery |
| EG028 | Имя не соответствует pattern | error | Pydantic |
| EG029 | Некорректная цепочка слоёв / конфликт layer merge | error | layers |
| EG030 | Неподдерживаемый режим/fallback | warning | engine |
| EG031 | Файл-слой содержит не одну сущность | error | layers |
| EG032 | Дубликат alias ресурса | error | resources |
| EG033 | Генератор не поддерживает формат сущности | error | engine |
| EG034 | Наследование/версии/схемы форматов | error | formats |
| EG035 | Дельта не добавляет ничего | warning | layers |
| EG036 | Glob без совпадений | warning | discovery |
| EG037 | Неизвестный `models.<dir>` | error | discovery |
| EG038 | Путь одновременно в `files` и `resources` | error | discovery |
| EG040 | Некорректный artifact path / content | error | write |
| EG041 | Ownership-конфликт / `on_conflict: error` | error | write |
| EG042 | Дубликат artifact path / case-collision / prefix | error | planning |
| EG043 | `skip` для не-owned файла | warning | planning |
| EG050 | Changed owned-файл не удалён при cleanup | warning | cleanup |
| EG051 | Stale generated location | warning | cleanup |
| EG052 | Manifest повреждён / версия не поддерживается | error | manifest |
| EG300 | Генератор/запись/check упали или drift | error | engine |
| EG301 | Нарушен контракт генератора | error | plugin |
| EG302 | Неизвестный инжектируемый параметр | error | plugin |

- Pydantic-ошибки маппятся в EG028/EG3xx с локацией.
- `format_plugin.validate(document)` вызывается после базовой структурной валидации; его `Diagnostic[]` объединяются с ядровыми.
- `--strict` повышает warning → error с учётом `rules.diagnostics.ignore`.
- Pydantic отвечает за структуру; Validator — за семантику (cross-ref'ы, null-matrix, типы, constraints).
- `validate()` не мутирует модель.

---

## 4.5 Model units и слои форматов

Новая модель сборки (v2.2):

```text
sources[].layout
   │
   ├── monolith
   │     └── один YAML → ModelDocument (несколько Entity)
   │
   ├── file-per-model
   │     └── каждый YAML → ModelDocument (одна Entity)
   │
   └── directory-per-model
         ├── model_dirs → каталоги моделей
         ├── files → YAML-слои
         ├── resources → ImportedFile[]
         └── для каждой модели:
               1. resolve version: explicit or latest
               2. если один файл — полный, validate full_entity
               3. если несколько:
                  ├── базовый файл → validate full_entity
                  ├── дельты → validate layer_entity
                  ├── order by format.extends
                  ├── check base_versions chain
                  ├── merge layers (ADR-0008)
                  └── validate full_entity
```

**Ресурсы:** top-level `resources` — относительно каталога конфига; `models.<dir>.resources` —
относительно каталога модели. Alias по умолчанию — путь без расширения (для модели с префиксом
`<dir>/`); `as` только для одного файла; коллизия — EG032. Ресурсы попадают в
`GenerationContext.imports` и watch.

`monolith` и `file-per-model` всегда дают полный файл: layer merge не выполняется,
пользователь пишет данные в конечном формате.

**Инварианты:**

- один файл — один формат; дубликат формата в модели — EG029;
- форматы слоёв образуют одну цепочку `extends`; иначе EG029;
- слой содержит ровно одну Entity — EG031;
- итоговый формат — самый производный; `Entity.format`/`format_version`;
- пустой каталог модели — Warning EG027;
- ресурсы не парсятся и не мержатся; alias коллизия — EG032;
- при смешанных форматах генератор проверяется по каждой Entity через `input_formats`;
  несовместимость — EG033.

**Merge слоёв** — аддитивный, без переопределений: новые поля/enum-значения/types/metadata-ключи;
конфликт значений — EG029. Скаляр можно задать только если он не задан в базовом слое.

**Коллекции и merge:**

- `KEYED` — расширяемый список: патч существующих + новые; `entity.fields`, `model.entities`.
- `APPEND` — append-only: только новые элементы; `model.enums`, `enum.values`, `model.types`.
- `UNION` — уникальные скаляры.
- `ERROR` — фиксированный кортеж; `imports` в слоях.
- Порядок базы сохраняется, новые элементы добавляются в конец.
- Существующий элемент `KEYED` мержится рекурсивно; дубликат ключа — EG029.
- `APPEND`: существующие элементы менять нельзя, повторный ключ — EG029.
- Политика задаётся через `json_schema_extra={"merge": ..., "merge_key": ...}`;
  неизвестный список без политики — `ERROR` (EG029).
- `metadata` списки — `APPEND`, словари — рекурсивно, конфликт скаляров — EG029.

---

## 5. Configuration Layer

### 5.1 AppConfig (pydantic-settings, v2-стиль)

```python
# eggpipe/config/app_config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EGGPIPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_destination: str = "stderr"       # stderr | stdout | file:./eggpipe.log

    rules_file: Path | None = None         # -c / --config

    debug: bool = False
    verbose: bool = False
    quiet: bool = False
    watch_debounce_ms: int = 300
```

- Приоритет: CLI-флаги → env → `.env` → defaults. Отдельного app-config-файла нет; `.eggpipe.yaml` — это `ProjectConfig`.
- `plugins_dir` и `cache_dir` **удалены**: плагины из директорий с ручным `sys.path` не поддерживаются (§6.3); кэш — future.
- `config_file` переименован в `rules_file`, чтобы не путать с app config.
- CLI собирает `AppConfig` после парсинга аргументов и передаёт override'ы в `Engine`.

### 5.2 ProjectConfigLoader

```python
class ProjectConfigLoader:
    def load(self, path: Path) -> ProjectConfig:
        data = load_yaml(path)                  # ruamel.yaml, duplicate keys → error
        try:
            return ProjectConfig.model_validate(data)
        except ValidationError as e:
            raise ConfigValidationError.from_pydantic(e, path) from e

    @classmethod
    def discover(cls, start: Path = Path.cwd()) -> Path | None:
        """Ищет .eggpipe.yaml от start вверх до git-root (или ФС-root)."""
```

- Относительные пути внутри `ProjectConfig` трактуются от `path.parent`.
- `discover()` возвращает путь, а не загруженный объект: Engine должен знать `config_dir`.
- Если конфигов несколько в цепочке — берётся ближайший; это фиксируется в `EngineReport`.
- `version` проверяется (`"1.0"`); неизвестная версия → EG3xx (exit 2).

### 5.3 Логирование (единая точка)

```python
def setup_logging(config: AppConfig) -> None:
    """Вызывается CLI. Библиотека этого не делает."""
    logger = logging.getLogger("eggpipe")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    dest = config.log_destination.lower()
    if dest == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    elif dest.startswith("file:"):
        handler = RotatingFileHandler(dest[5:], maxBytes=10 * 1024 * 1024, backupCount=5)
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(config.log_format))
    logger.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"eggpipe.{name}")
```

- В библиотеке `setup_logging()` не вызывается; на `eggpipe`-логгере висит `NullHandler`, `propagate` не ломает logging хоста.
- Никакого `logging.basicConfig(force=True)`.
- Логи не попадают на stdout (не ломается `--output-format json`) — только stderr/file.
- Значения `variables`, похожие на секреты, редактируются в логах и `config show`.

---

## 6. Plugin Loader

### 6.1 Entry points

```python
class PluginLoader:
    GROUP_GENERATORS = "eggpipe.generators"
    GROUP_FORMATS    = "eggpipe.formats"
    SUPPORTED_API    = frozenset({"1"})

    def discover(self) -> list[PluginInfo]:
        """Загружает классы, но не инстанцирует; ошибки — в PluginInfo, не падают."""

    def get_generator(self, generator_id: str) -> GeneratorPlugin:
        """Ленивая загрузка выбранного генератора; incompatible/import error → exit 2."""

    def load_formats(self) -> list[FormatPlugin]:
        """Нужны для парсинга; конфликт имён — EG007."""
```

- `PluginInfo`: `id`, `name`, `distribution`, `version`, `api_version`, `status` (`ok|incompatible|error`), `error`.
- `ep.load()` может кинуть любое исключение: оно превращается в `PluginLoadError` и показывается в `eggpipe gen list`; **не ломает** запуск, если плагин не выбран.
- `plugin.id != ep.name` → **Error** (не Warning): id — часть контракта.
- Дубликат `id` из разных distribution'ов → **Error** с перечнем distribution'ов; silent overwrite запрещён.
- Несовместимый `api_version`:
  - не выбран — `status="incompatible"` + Warning в списке;
  - выбран (`-g`) или `enabled: true` в конфиге — exit 2.
- `EXPECTED_API_VERSION` — множество поддерживаемых; ошибка содержит distribution, версию плагина и требуемую версию ядра.
- Плагины сортируются по `id` для детерминизма.
- `eggpipe gen list` не инстанцирует плагины; `eggpipe gen info <id>` — инстанцирует.
- Формат-плагины загружаются eagerly (нужны для парсинга), но ошибка одного не должна мешать `eggpipe gen list`; для `generate` достаточно форматов, используемых в sources.

### 6.2 Регистрация (pyproject.toml проекта-плагина)

```toml
[project.entry-points."eggpipe.generators"]
oracle-ddl = "my_oracle_generator:MyGenerator"

# для новых форматов:
[project.entry-points."eggpipe.formats"]
sql-model = "my_oracle_generator.format:SqlModelFormat"
```

### 6.3 Локальная разработка плагина

`sys.path`-хаки и `plugins_dir` **не поддерживаются**. Дев-цикл:

```bash
pip install -e ./plugins/my-generator   # editable install
eggpipe gen list                             # плагин виден
```

(`--plugin path/to/module.py` — dev-only загрузка через importlib spec, без правки `sys.path`.)

---

## 7. CLI (Typer)

### 7.1 Структура команд

```python
app = typer.Typer(name="eggpipe", help="Eggpipe", no_args_is_help=True)
app.add_typer(config_app, name="config")   # show, validate
app.add_typer(model_app,  name="model")    # validate, schema
app.add_typer(gen_app,    name="gen")      # list, info
app.add_typer(format_app, name="format")   # list

@app.command()
def generate(
    models: Optional[list[Path]] = typer.Argument(None),
    generator: Optional[list[str]] = typer.Option(None, "-g", "--generator"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    output: Optional[Path] = typer.Option(None, "-o", "--output"),
    var: Optional[list[str]] = typer.Option(None, "--var", help="KEY=VALUE, многократно"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    plan: bool = typer.Option(False, "--plan"),
    check: bool = typer.Option(False, "--check"),
    clean: bool = typer.Option(False, "--clean"),
    strict: bool = typer.Option(False, "--strict"),
    ignore: Optional[list[str]] = typer.Option(None, "--ignore", help="коды EG..., многократно"),
    force: bool = typer.Option(False, "--force"),
    yes: bool = typer.Option(False, "--yes"),
    include_disabled: bool = typer.Option(False, "--include-disabled"),
    allow_outside_imports: bool = typer.Option(False, "--allow-outside-imports"),
    output_format: str = typer.Option("text", "--output-format"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    no_color: bool = typer.Option(False, "--no-color"),
):
    """Генерация артефактов."""

@app.command()
def watch(models: Optional[list[Path]] = typer.Argument(None), ...): ...

@app.command()
def init(force: bool = typer.Option(False, "--force")): ...

@app.command()
def clean(
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
): ...
```

- `-g a,b` и повторяющийся `-g a -g b` — оба варианта; split по запятой с trim.
- Позиционные `models` заменяют `sources`; `generators[].input` применяется, `sources[].input` — нет.
- `--format` переименован в `--output-format`, чтобы не путать с форматом документа.
- `--plan`/`--dry-run` — синонимы; `--plan` печатает create/update/skip/delete/conflict.
- `--check` не пишет файлы; drift → exit 1.
- `--clean` — разовый cleanup текущего запуска; `eggpipe clean` — все манифесты.
- `eggpipe init` не перезаписывает файл без `--force`.
- `eggpipe config show` показывает resolved paths и redact секретов; `--output-format json`.
- `eggpipe model validate` принимает несколько файлов/каталогов; `--output-format json`.

### 7.2 Выходные коды и поведение при ошибках

| Ситуация | exit code |
|----------|-----------|
| Успех | 0 |
| Ошибки парсинга/валидации/генерации, drift `--check`, warnings при `--strict` | 1 |
| Config/usage: нет `.eggpipe.yaml`, неизвестный generator id, `--var` без `=`, `api_version` mismatch, ошибка выбранного плагина, ошибка схемы `.eggpipe.yaml`, EG033/EG034/EG301/EG302 | 2 |
| Ctrl+C | 130 |

Ошибка одного генератора: логируется, остальные продолжаются (aggregate отчёт в конце).
`diagnostics.ignore`/`--ignore` игнорируют только warnings; errors показываются всегда.
`--strict` повышает warnings до errors после фильтрации.

### 7.3 `--var`

```python
def parse_vars(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise UsageError(f"`--var` expects KEY=VALUE, got: {item}")   # exit 2
        out[key.strip()] = value          # последний дубликат побеждает
    return out
```

Приоритет: CLI `--var` > `.eggpipe.yaml variables`. Все значения — строки. Результат — `GenerationContext.variables`. Ядро не подставляет vars в пути/шаблоны само — это решение плагина. Секреты не логируются.

### 7.4 Formatters и EngineReport

```python
class OutputFormatter(ABC):
    @abstractmethod
    def format(self, report: EngineReport) -> str: ...

class TextFormatter(OutputFormatter): ...    # план, [✓] generator → dir/, сводка
class JsonFormatter(OutputFormatter): ...    # только JSON в stdout
```

```json
{
  "report_version": 2,
  "success": true,
  "exit_code": 0,
  "run_id": "01J...",
  "diagnostics": [
    {"level": "warning", "code": "EG012", "message": "...", "location": {"file": "model.yaml", "entity": "User"}}
  ],
  "formats": [
    {"name": "entity-model", "version": "1.0", "entities": 2}
  ],
  "generators": [
    {
      "id": "oracle-ddl",
      "name": "Oracle DDL",
      "status": "ok",
      "input_formats": ["entity-model"],
      "formats": [{"name": "entity-model", "version": "1.0"}],
      "duration_ms": 42
    }
  ],
  "artifacts": [
    {"generator": "oracle-ddl", "path": "user.sql", "action": "create", "sha256": "..."}
  ],
  "manifest": {
    "manifest_version": 2,
    "locations": [
      {"generator": "oracle-ddl", "output_dir": "output/oracle", "artifacts": 1}
    ]
  },
  "stale_locations": [],
  "timings": {
    "discovery_ms": 1,
    "parse_ms": 12,
    "validate_ms": 2,
    "generate_ms": 55,
    "write_ms": 3,
    "total_ms": 73
  }
}
```

- `EngineReport` — общий результат запуска (не путается с `GenerationResult` одного плагина).
- `report_version: 2`; `artifacts` — плоский список с `generator`, без дублирования в `generators[]`.
- `artifacts[].action` — `create|update|skip|delete|conflict|error|drift`;
  `generators[].status` — `ok|error|skipped`.
- `timings` содержит обязательные `discovery_ms`, `parse_ms`, `validate_ms`, `generate_ms`,
  `write_ms`, `total_ms`.
- `formats` — глобальная сводка; `manifest` — только locations; `stale_locations` — для EG051.
- JSON-отчёт печатается только в stdout; логи — stderr/file.
- `--quiet` подавляет человекочитаемый вывод, но не JSON.
- Порядок `generators`/`artifacts` детерминирован (по id/path).
- Пути — относительные POSIX от каталога конфига.

---

## 8. Artifact Writer

### 8.1 Валидация путей

```python
WINDOWS_RESERVED_NAMES = {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)} | {"CON", "PRN", "AUX", "NUL"}

def validate_artifact_path(output_dir: Path, artifact: Artifact) -> Path:
    p = PurePosixPath(artifact.path)
    if p.is_absolute() or not p.parts:
        raise ArtifactPathError(EG040, artifact, "path must be relative")
    for part in p.parts:
        stem = part.split(".", 1)[0].upper()
        if (part in {"", ".", ".."} or part.startswith(".eggpipe") or stem in WINDOWS_RESERVED_NAMES
                or part.endswith((" ", ".")) or "\x00" in part or "\\" in part):
            raise ArtifactPathError(EG040, artifact, "invalid path segment")
    if len(str(p)) > 4096 or any(len(part) > 255 for part in p.parts):
        raise ArtifactPathError(EG040, artifact, "path too long")

    output_resolved = output_dir.resolve()
    target = (output_resolved / p).resolve()
    if not target.is_relative_to(output_resolved):
        raise ArtifactPathError(EG040, artifact, "escapes output_dir")  # '..' / symlink
    return target
```

Дополнительно:

- Путь нормализуется в NFC; внутри одного запуска и в общем `output_dir` проверяются case-insensitive коллизии (EG042).
- Symlink-родитель, ведущий наружу, отклоняется; проверка повторяется непосредственно перед записью.
- `content` проверяется на `str`, UTF-8, LF, отсутствие BOM.
- Дубликаты `path` внутри `GenerationResult` — EG042.

### 8.2 Planning, ownership и on_conflict

До записи Engine строит `ExecutionPlan` и глобальную карту путей.

```python
@dataclass(frozen=True)
class PlannedArtifact:
    generator_id: str
    output_dir: Path
    path: PurePosixPath
    action: Literal["create", "update", "skip", "delete", "conflict"]
    sha256: str

@dataclass
class ExecutionPlan:
    artifacts: list[PlannedArtifact]
    conflicts: list[Diagnostic]
```

- Глобальный manifest `.eggpipe/manifest.json` загружается один раз.
- Location = `(generator, output_dir)`.
- `owned` = пути из artifacts этого location.
- До записи проверяются exact, casefold и prefix-конфликты (`foo` vs `foo/bar`) между
  всеми планами — EG042.
- `on_conflict`:

| `on_conflict` | Файл существует и owned текущим location | Файл существует и не owned |
|---|---|---|
| `overwrite` (default) | перезаписать | **EG041**, только с `--force` |
| `skip` | не трогать, записать в manifest с текущим sha256 | не трогать, **не** добавлять в manifest; Warning EG043 |
| `error` | EG041, генератор не пишет | EG041 |

- `--force` разрешает перезапись только **unowned** файла; после записи файл становится owned.
- `--force` не отбирает файл у другого generator/location: EG041, сначала `eggpipe clean`.
- `--check` сравнивает план с диском и manifest; drift → exit 1.

### 8.3 Manifest

Один глобальный manifest: `.eggpipe/manifest.json` в каталоге конфига.

```json
{
  "manifest_version": 2,
  "locations": [
    {
      "generator": "oracle-ddl",
      "output_dir": "output/oracle",
      "eggpipe_version": "0.3.2",
      "plugin_version": "1.2.0",
      "formats": [{"name": "entity-model", "version": "1.0"}],
      "generated_at": "2026-11-11T12:34:56Z",
      "artifacts": [{"path": "user.sql", "sha256": "...", "skipped": false}]
    }
  ]
}
```

- Ключ location — `(generator, output_dir)`.
- Пишется после успешной записи артефактов каждого генератора, атомарно (temp → `os.replace`).
- `skipped: true` — ядро не писало файл; cleanup такие записи не удаляет.
- `.eggpipe/` рекомендуется в `.gitignore`; manifest не предназначен для коммита.
- `--check` и `--plan` не обновляют manifest.
- Manifest v1 не поддерживается.

### 8.4 Atomicity и блокировки

```python
with global_lock(config_dir):                 # .eggpipe/lock
    for generator in generators:
        with staging_dir(output_dir) as staging:
            write_all(staging, artifacts)
            for path in artifacts:
                os.replace(staging / path, output_dir / path)
        update_global_manifest(location)      # atomic temp → replace
```

- Staging — внутри `output_dir` (та же ФС), имя `.eggpipe-staging-<pid>-<uuid>`.
- Сначала все проверки конфликтов, потом запись. Ошибка до записи не оставляет файлов.
- Batch-транзакции нет: при аварии посреди `os.replace` возможен частично обновлённый набор;
  manifest обновляется после каждого генератора, следующий запуск обнаружит drift по sha256.
- Staging удаляется при старте и по сигналу.
- Lock: глобальный `.eggpipe/lock` (O_EXCL, PID) в каталоге конфига; `generate`/`clean` сериализованы.
- `--dry-run`/`--plan`/`--check` не создают каталоги, не берут lock и не меняют файлы.

### 8.5 Cleanup

- Cleanup работает **только с owned-артефактами из глобального manifest**; не сканирует `output_dir`.
- `skipped: true` не удаляется никогда — это файлы, которые ядро не писало.
- Кандидат — запись location (`skipped: false`), которой нет в текущем результате генератора.
- Cleanup в рамках `generate` — только для текущего location успешно завершившегося генератора.
- Удаляется только если текущий sha256 совпадает с manifest; иначе Warning EG050, файл сохраняется.
- `cleanup: off` — default; `prompt` — fallback off + EG030; `enabled` — удалять unchanged stale.
- `eggpipe generate --clean` — разово `enabled`.
- `eggpipe clean`:
  - работает только по `.eggpipe/manifest.json`, без `.eggpipe.yaml` и плагинов;
  - обходит все locations, включая удалённые генераторы и старые `output_dir`;
  - удаляет unchanged owned-артефакты; изменённые — EG050;
  - удаляет пустые locations; если locations не осталось — удаляет manifest;
  - `--dry-run` показывает план; вне tty нужен `--yes`.
- Если `output_dir` изменился, старый location остаётся; при генерации — Warning EG051.
- Если генератор удалён из конфига, его location остаётся до `eggpipe clean`.

---

## 9. Watch Mode

### 9.1 File Watcher (lazy import)

```python
class Watcher:
    """watchdog Observer + DebounceHandler(debounce_ms).
    import watchdog — лениво, чтобы CLI не платил стартовой ценой пакета."""

    def __init__(
        self,
        watch_paths: list[Path],
        *,
        ignore: list[Path],
        debounce_ms: int = 300,
    ): ...

    def run(self, callback: Callable[[set[Path]], None]) -> None: ...
```

### 9.2 Поведение

- **Первичная генерация** выполняется сразу при старте `eggpipe watch` (как `eggpipe generate` с теми же флагами).
- **Наблюдаемые пути:** все `sources.path` (файлы и каталоги), импортируемые YAML-модели, `.eggpipe.yaml`, файлы шаблонов, указанные в `options` генераторов (если плагин сообщает их через `watch_paths` — future; v1 наблюдает только модели и конфиг).
- **Игнорируются:** все `output_dir` текущего конфига, `.git`, `.eggpipe`, `__pycache__`, `.venv`, `venv`, `node_modules`, `*.tmp`, `*.swp`, `*~`.
- **Debounce:** изменения батчатся за `watch_debounce_ms` (default 300); на батч выполняется одна генерация.
- **Перезагрузка конфига:** изменение `.eggpipe.yaml` (или `-c`-файла) перезагружает `ProjectConfig`; **плагины не перезагружаются** — для обновления кода плагина нужен перезапуск (сообщается в лог).
- **Ошибки не останавливают watch:** ошибка парсинга/валидации/генерации логируется; следующие изменения снова запускают цикл.
- **Флаги:** те же, что у `generate` (`-g`, `--var`, `--strict`, `--output-format`, `--include-disabled`, `--allow-outside-imports`).
- **Завершение:** Ctrl+C — корректная остановка Observer, удаление lock/staging, exit 0; прерывание по сигналу — 130.
- **`--output-format json` в watch:** каждая итерация печатает отдельный JSON-объект (JSON Lines), без цветов и человекочитаемого текста.

### 9.3 Интерфейс для будущего кэширования

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

```text
src/eggpipe/
├── __init__.py                  # публичный API, __all__
├── py.typed
├── cli/main.py                  # typer app и все команды
├── config/
│   ├── app_config.py            # AppConfig
│   ├── project_config.py        # ProjectConfig, ProjectConfigLoader
│   └── logging.py               # setup_logging()
├── core/
│   ├── document.py              # ModelDocument, ImportSpec
│   ├── model.py                 # SourceModel, ModelSlice, Entity, FieldDef, ...
│   ├── parser.py                # Parser, header, imports
│   ├── discovery.py             # layouts, model units, resources
│   ├── paths.py                 # shared ignore rules for discovery/watch
│   ├── layers.py                # layer validation/merge
│   ├── composition.py           # imports/extends, merge, closure
│   ├── slicing.py               # select_slice()
│   ├── validator.py             # semantic validation
│   ├── naming.py                # NamingStyle, transform()
│   ├── provenance.py            # git_provenance()
│   └── format_registry.py       # FormatRegistry
├── engine/
│   ├── engine.py                # Engine facade and orchestration
│   ├── artifact_writer.py       # plan, atomic write, manifest, cleanup, lock
│   ├── plugin_loader.py         # entry points (generators + formats)
│   ├── policy.py                # DiagnosticPolicy
│   └── report.py                # EngineReport and JSON DTOs
├── interfaces/
│   ├── generator.py             # GeneratorPlugin, @generator, GeneratorInput
│   ├── formats.py               # FormatPlugin, EntityModelFormat
│   └── diagnostics.py           # Diagnostic, DiagnosticLocation
├── watch/watcher.py             # WatchRunner, debounce
├── utils/
│   ├── yaml.py                  # load_yaml() поверх ruamel.yaml
│   └── exceptions.py
└── templating.py                # optional Jinja2 helper

tests/                           # flat suite: unit, contract, security, golden, property
examples/
├── reference-generator/
├── tpc-h-generator/
└── tpc-h/
docs/
├── requirements/                # index, v1.0–v1.4, v2.0, v2.1, v2.2
├── system-design/
├── reviews/
├── adr/
└── reference/
tools/
├── check_docs.py
└── check_wheel.py
.github/workflows/               # docs, ci, release
pyproject.toml
pyrightconfig.json
uv.lock
README.md
CONTRIBUTING.md
CHANGELOG.md
LICENSE
```

Отдельных `cli/*_cmds.py`, `engine/planning.py`, `engine/locking.py`, `watch/cache.py`
в v2.2 нет: команды находятся в `cli/main.py`, planning/lock — в `artifact_writer.py`,
cache остаётся future-направлением.

---

## 11. Тестирование (охват v2.2)

### 11.1 Приоритеты

1. **Golden-file**: fixtures → expected artifacts (главная защита от регрессии артефактов). Так как встроенных генераторов нет, golden-тесты используют **reference-плагин** из `examples/`.
2. Merge-семантика ADR-0001 и layer merge ADR-0008 — тесты на каждое правило.
3. **Null-matrix** — все 12 комбинаций из ТЗ §3.6, включая `UNSET` vs explicit `null`.
4. Parser: simple / imports / entity.extends / cycle / depth / unknown format / unknown version / duplicate keys / YAML 1.2-скаляры.
5. **Форматы v2.2**: наследование, цикл/глубина, `input_formats`, совместимость генератора, смешанные форматы в запуске (EG033).
6. **Model units**: `monolith`/`file-per-model`/`directory-per-model`, `model_dirs`/`files`/`resources`, пустой каталог, duplicate format, unrelated formats, layer entity count (EG027/EG029/EG031/EG032).
7. Integration CLI: полный цикл, exit codes, `--strict`, `--var`, `--dry-run`/`--plan`/`--check`, `--include-disabled`.
8. **Contract-тесты plugin API**: reference-generator и reference-format проходят публичный контракт; несовместимый `api_version` ведёт себя по §6.
9. **Security**: path traversal, symlink-выход из `output_dir`, импорт вне project root, duplicate keys, YAML-алиасы (billion laughs), секреты в логах.
10. **Cleanup**: modified owned-файл не удаляется (EG050), чужой файл не удаляется, shared `output_dir`, удалённый из конфига генератор.
11. **Concurrency**: второй запуск при held lock; stale lock.
12. **Determinism**: повторный запуск даёт идентичные байты; порядок source/artifact/plugin стабилен; артефакты не содержат абсолютных путей.

### 11.2 Property-based

```python
@given(st.dictionaries(keys, values))       # ЛЮБОЙ dict
def test_never_crashes_on_arbitrary_input(data):
    """Parser на произвольном dict кидает только доменные ошибки
    (DocumentError/ValidationError), не KeyError/TypeError/AttributeError."""

@given(valid_model_data())                   # стратегия строит валидные модели
def test_round_trip(data) -> None:
    document = ModelDocument.model_validate(data)
    assert ModelDocument.model_validate(document.model_dump(mode="json")) == document

@given(valid_model_data())
def test_all_valid_models_pass_validation(data) -> None:
    assert not [d for d in validate(...) if d.level == "error"]

@given(invalid_model_data())
def test_invalid_models_produce_expected_code(data) -> None:
    assert expected_code in {d.code for d in validate(...) if d.level == "error"}
```

Стратегия валидных данных комбинирует entity names/fields/types/enums/constraints и учитывает null-matrix и `UNSET`; round-trip сравнивается с учётом `date`/`datetime` и заполнения enum values.

### 11.3 Производительность

- **Модель для замеров:** 1000 entities, 100 enums, 100 types, ~20 полей на entity.
- **Методика:** прогрев + 5 прогонов, берётся медиана; фиксируется reference-машина и версия Python в CI.
- **Бюджеты:** parse+compose+validate ≤ 500 мс; slice+closure ≤ 100 мс; overhead ядра на генератор ≤ 50 мс.
- **Регрессия:** деградация > 20% между релизами — повод разобраться; бюджет уточняется после прототипа.
- Отдельно проверяется lazy-import: `eggpipe --help` не должен импортировать `watchdog`.

---

## 12. Зависимости (pyproject.toml)

```toml
[project]
name = "eggpipe"
version = "0.3.2"
description = "CLI tool and library for metadata-driven code generation"
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.11"
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Programming Language :: Python :: 3.15",
    "Typing :: Typed",
]
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "ruamel.yaml>=0.18.6",
    "rich>=13.7.0",
    "typing-extensions>=4.10.0",
]

[project.optional-dependencies]
watch = ["watchdog>=4.0.0"]
jinja = ["jinja2>=3.1.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.100.0",
    "ruff>=0.4.0",
    "pyrefly>=1.4.0",
    "watchdog>=4.0.0",
    "mkdocs>=1.6.0",
    "jinja2>=3.1.0",
]

[project.scripts]
eggpipe = "eggpipe.cli.main:app"

[project.urls]
Homepage = "https://github.com/<org>/eggpipe"
Documentation = "https://github.com/<org>/eggpipe/tree/main/docs"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/eggpipe"]

[tool.hatch.build.targets.sdist]
exclude = [".github", ".opencode", ".session-context.md", "opencode.json", "AGENTS.md"]
```

Конфигурация инструментов:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pyrefly]
python-version = "3.11"
preset = "strict"
project-includes = ["src", "tests", "tools"]
search-path = ["src", "."]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- Типизация проверяется **Pyrefly** (`preset = "strict"`), см. [ADR-0002](../adr/0002-type-checker-pyrefly.md).
  mypy не входит в блокирующий CI; `py.typed` сохраняет совместимость с другими чекерами.
- Для basedpyright/Pyright в корне лежит `pyrightconfig.json`: src-layout, `extraPaths` и `.venv`.
- Dev/CI используют **uv** (`uv sync --extra dev`, `uv run`), `uv.lock` коммитится.
  Для установки пакета пользователями остаётся `pip install eggpipe`.
- Сборка проверяется `tools/check_wheel.py`: wheel содержит `py.typed` и LICENSE, метаданные
  зависимостей корректны, sdist не содержит dev-harness; выполняется smoke-install в чистом venv.
- Команда `eggpipe` определена в `[project.scripts]` и проверяется при сборке wheel.
- `watchdog` — **optional extra** `[watch]`, lazy-import в `watch/watcher.py`; без `eggpipe watch` пакет не требуется.
- `ruamel.yaml` (YAML 1.2) вместо PyYAML: duplicate keys → ошибка, корректные `yes/no`, даты.
- Пакет поставляет `py.typed` (PEP 561); публичный API — `__all__` в `__init__.py`.
- Python 3.11+ — ради `StrEnum`, `Self`, `tomllib`, современных Pydantic v2; CI проверяет 3.11–3.15.
- Встроенных генераторов и `[project.entry-points]` в ядре нет: entry points регистрируют плагины.

---

## 13. Проектировочные решения (v2.2, сводка)

| Решение | Причина | Где |
|---------|---------|-----|
| Явные `ModelDocument` → `SourceModel` → `ModelSlice` | Разная ответственность и гарантии на каждом этапе | ТЗ §3.1, §2.1 |
| Заголовок документа: `format` обязателен, `version` опционален (latest); `metadata` — extension point | Наследование формата — зона формат-плагина | ТЗ §3.4 |
| Форматы могут наследоваться; генератор объявляет `input_formats` | Один генератор для базового формата принимает расширения | ADR-0007, ТЗ §3.4 |
| Модель = одна сущность; слои форматов мержатся аддитивно | Один входной YAML на сущность без копий под генераторы | ADR-0008, ТЗ §3.5 |
| Смешанные форматы в запуске; несовместимость — EG033 | Постепенное расширение модели без общего «целевого формата» | ADR-0007 |
| `UNSET` отличается от `default: null` | Null-matrix должна различать «не задан» и «null» | ТЗ §3.6, §3.1 |
| Сущности изолированы (без relations в базе) | Нейтральность ядра | ТЗ §1.1 |
| Два типа плагинов (generators, formats) | Реестр форматов расширяем | §6 |
| Вход генератора — замкнутый срез (`ModelSlice`) | Cross-entity артефакты + корректные ссылки на enums/types | ТЗ §5 |
| App-config плагину не передаётся | Чистый публичный контракт | §2.1 |
| Имена файлов задаёт плагин, ядро валидирует пути | Нет двух источников имён | §8.1 |
| `naming_convention` — подсказка в context | Не переименовывать модель молча | §2.6 |
| Плагин `api_version` через `ClassVar` | Обратная совместимость контракта | §6.1 |
| Ownership + global manifest | Безопасная перезапись и cleanup в общем `output_dir` | §8.2–8.3 |
| `cleanup: off` по умолчанию, удаление только unchanged owned-файлов | Защита пользовательских файлов | §8.5 |
| Atomic write + staging + lock | Безопасная запись и защита от параллельных запусков | §8.4 |
| `--plan`/`--check` без побочных эффектов | CI и предсказуемость | §7.1 |
| `ruamel.yaml`, YAML 1.2, duplicate keys → error | Однозначность и отсутствие «тихих» потерь | §4.1 |
| Локальные плагины через pip -e, не sys.path | Стандарт, без хаков | §6.3 |
| Логи в stderr/file, CLI-вывод в stdout (rich) | Совместимость с `--output-format json` | §5.3 |
| `Engine` как библиотечный фасад без `sys.exit`/root-logger | First-class библиотечное использование | §2.8 |
