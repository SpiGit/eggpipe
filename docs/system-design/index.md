# System Design — Metadata Generator

> Документ реализации для проекта metadata-generator. Соответствует [ТЗ v1.3](../requirements/v1.3.md). Правила композиции — [ADR-0001](../adr/0001-composition-merge-semantics.md).

*Версия документа: 1.3. Дата: 2026-11-11.*

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
| **Config** | AppConfig (CLI → env → .env → defaults) + GeneratorRules (.mg.yaml) |
| **Engine** | Оркестрация: парсинг → composition → validate → generate → write |
| **FormatRegistry** | Реестр форматов: встроенный `entity-model` + форматы от формат-плагинов |
| **Parser** | YAML parse, imports, entity.extends |
| **Composition** | Merge по правилам ADR-0001 |
| **Validator** | Кросс-сущностные проверки: warnings + errors (null-matrix, дубликаты, unused, stale dates) |
| **Plugin Loader** | Ленивая загрузка плагинов из entry points, проверка `api_version` |
| **Planning** | План create/update/skip/delete, ownership и конфликты до записи |
| **Lock** | `.mg/lock` — защита от параллельной записи в один `output_dir` |
| **Artifact Writer** | Проверка путей, on_conflict, atomic write, per-generator manifest, cleanup |
| **Plugins** | Генераторы (и формат-плагины) — код + шаблоны |

### 1.2 Поток данных

```
1. CLI получает команду
        │
2. AppConfig создаётся (CLI → env → .env → defaults)
        │
3. GeneratorRulesLoader загружает .mg.yaml
        │
4. Для каждого source:
    ├── FormatRegistry выбирает формат (по header `format`, без default)
    ├── Parser парсит YAML → ModelDocument (imports, entity.extends —
    │   рекурсивно, правила merge: ADR-0001)
    └── Validator: структурные (Pydantic) + semantic проверки
        │
5. Composition собирает SourceModel из sources (union),
   валидирует глобальные инварианты (дубликаты имён между source)
        │
6. Plugin Loader загружает выбранные генераторы (lazy, api_version)
        │
7. Для каждого генератора:
    ├── Engine вычисляет срез + closure → ModelSlice
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

> Публичный API ядра экспортирует **только** эти контракты (из `metadata_generator.__init__`): `GeneratorPlugin, GeneratorInput, GenerationResult, Artifact, GenerationContext, ImportedFile, SourceModel, ModelSlice, Entity, FieldDef, EnumDef, CustomType, GeneratorConfig, NamingStyle, transform, Diagnostic, EngineReport, Engine, AppConfig, GeneratorRules, GeneratorRulesLoader, FormatRegistry` и базовые исключения. Всё остальное — внутреннее и может меняться. Пакет поставляет `py.typed`.

### 2.1 GeneratorInput — вход генератора

```python
class GeneratorInput(BaseModel):
    """Immutable входные данные генератора."""
    model: ModelSlice            # замкнутый срез: entities/enums/types
    config: GeneratorConfig      # свой блок из .mg.yaml (id, options, output_dir, ...)
    context: GenerationContext   # variables, format, imports, source paths

    model_config = ConfigDict(frozen=True)
```

**AppConfig в плагин не передаётся** — технические настройки вне клиентского контракта.

### 2.2 GenerationContext

```python
class GenerationContext(BaseModel):
    """Контекст генерации; копируется на каждый генератор."""
    variables: dict[str, str] = {}       # --var ∪ .mg.yaml variables (CLI > config)
    naming_hint: NamingStyle | None     # defaults.naming_convention (подсказка!)
    imports: dict[str, ImportedFile]    # alias (as) → файл
    sources: list[Path]                 # относительные пути source-файлов (провенанс)
    format: str                         # имя формата документа
    format_version: str                 # версия схемы формата
    run_id: str                         # идентификатор запуска
    config_dir: Path                    # каталог .mg.yaml

    model_config = ConfigDict(frozen=True)

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

```python
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

API_VERSION = Literal["1"]

class GeneratorPlugin(ABC):
    api_version: ClassVar[Literal["1"]]   # ядро проверяет при загрузке
    id: ClassVar[str]                     # совпадает с entry point id
    name: ClassVar[str] = ""              # default → id

    @abstractmethod
    def generate(self, input: GeneratorInput) -> GenerationResult: ...

    def validate_config(self, config: GeneratorConfig) -> list[Diagnostic]:
        return []                         # semantic-ошибки конфига генератора
```

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
    supported_versions: ClassVar[list[str]]    # ["1.0"]
    primitive_types: ClassVar[set[str]]        # примитивы формата

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

- Format-плагин, расширяющий `entity-model`, наследует `EntityModelFormat` и переопределяет `parse_extensions`/`validate_extensions`.
- Format-плагин с полностью собственной схемой реализует `FormatPlugin` напрямую (без базовой валидации).
- Header `format`/`version` обязателен; неизвестная версия → MG008.
- `entity-model` зарезервирован; попытка переопределить — Error при регистрации.
- Дополнительные поля складываются в `metadata` сущности под namespace формата.
- Один запуск — один формат; смешивание — MG007.
- `format` и `version` передаются генератору через `GenerationContext`.

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
- Если `naming_convention` не задан, `naming_hint = None` (а не неявный SNAKE).
- Какую трансформацию куда применить — решает плагин (SQL table → snake, Pydantic class → pascal и т.п.).
- `transform` обязан быть детерминированным, сохранять цифры и корректно обрабатывать акронимы (`HTTPServer` → `http_server`/`HttpServer`); edge-cases покрываются тестами.

### 2.7 Пример генератора

```python
# my-generator/src/my_generator/__init__.py
from metadata_generator import (
    GeneratorPlugin, GeneratorInput, GenerationResult, Artifact,
    NamingStyle, transform,
)

class MyGenerator(GeneratorPlugin):
    api_version = "1"
    id = "my-generator"
    name = "My Generator"

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
        rules: GeneratorRules,
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
| `nullable=false` и `default is None` (ключ задан явно) | MG010 | Error |
| `required=true` и `nullable=true` | MG011 | Warning |
| `default is not UNSET` и тип не совпадает с итоговым `type` | MG016 | Error |
| `default` нарушает constraints/enum | MG017 | Error |

`default is UNSET` — валидное состояние для `required=false`, `nullable=false`: допустимость отсутствия значения определяет формат/генератор. Комбинация не является ошибкой ядра.

### 3.2 GeneratorConfig / GeneratorRules

```python
class InputSlice(BaseModel):
    entities: tuple[str, ...] | None = None   # None/пусто = все
    enums: tuple[str, ...] | None = None
    types: tuple[str, ...] | None = None
    model_config = ConfigDict(extra="forbid", frozen=True)

class GeneratorConfig(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    enabled: bool = True
    input: InputSlice = InputSlice()
    output_dir: Path                    # относительный путь
    on_conflict: Literal["overwrite", "skip", "error"] = "overwrite"
    cleanup: Literal["off", "prompt", "enabled"] = "off"
    options: dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)

class DefaultsConfig(BaseModel):
    naming_convention: NamingStyle | None = None   # подсказка; None = не задана
    model_config = ConfigDict(extra="forbid", frozen=True)

class SourceConfig(BaseModel):
    path: Path
    input: InputSlice = InputSlice()
    model_config = ConfigDict(extra="forbid", frozen=True)

class DiagnosticsConfig(BaseModel):
    stale_dates: bool = False              # MG014 opt-in
    ignore: frozenset[str] = frozenset()   # коды MG...
    model_config = ConfigDict(extra="forbid", frozen=True)

class GeneratorRules(BaseModel):
    version: Literal["1.0"]              # обязательна
    defaults: DefaultsConfig = DefaultsConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    variables: dict[str, str] = {}
    sources: tuple[SourceConfig, ...] = ()
    generators: tuple[GeneratorConfig, ...] = ()
    model_config = ConfigDict(extra="forbid", frozen=True)
```

Генератор **не имеет `source`** — работает с составленным целым. `sources[].input` фильтрует содержимое своего source; итоговая модель — union отфильтрованных источников. Срез генератора = `generators[].input` по этой модели + closure.

`output_dir` обязан быть относительным (абсолютный → MG3xx, exit 2); `-o` заменяет базу, относительные пути резолвятся от `config_dir`.

Нейминг: `GeneratorRulesLoader` (не `BusinessConfigLoader`), файл `config/generator_rules.py`.

### 3.3 Преимущества Pydantic (с охватом v1.3)

| Возможность | Как |
|-------------|-----|
| Структурная валидация | `model_validate`, `extra="forbid"`, pattern |
| Различение `UNSET`/`null` | sentinel + `model_fields_set` |
| Type-references | строки + `validator.py` |
| YAML → Model | `ModelDocument.model_validate(...)` |
| Понятные ошибки | `e.errors()` → `ConfigValidationError` (MG3xx) |
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
            raise DocumentError(MG000, path, "document root must be a mapping")
        fmt = data.get("format")
        if not fmt:
            raise DocumentError(MG007, path, "`format` is required")
        version = normalize_version(data.get("version"))   # 1.0 → "1.0"
        if version is None:
            raise DocumentError(MG008, path, "`version` is required")
        plugin = self.registry.get(fmt)      # UnknownFormatError → MG007
        if version not in plugin.supported_versions:
            raise DocumentError(MG008, path, f"{fmt} does not support {version}")
        document = plugin.parse(data, base_path=path.parent)
        return document
```

YAML-загрузчик:

- `ruamel.yaml` в safe-режиме (YAML 1.2).
- `allow_duplicate_keys=False` → MG000.
- multi-document (`---`) → MG000.
- не-dict корень → MG000.
- `version` принимает строку или число и нормализуется; иначе MG008.
- абсолютные пути импортов запрещены; см. §4.2.

Реестр:

```python
class FormatRegistry:
    """Встроенный 'entity-model' + форматы от формат-плагинов."""
    def register(self, name: str, plugin: FormatPlugin) -> None:
        # duplicate name → FormatConflictError (MG007)
        # name == "entity-model" для внешнего плагина → MG007
    def get(self, name: str) -> FormatPlugin: ...   # UnknownFormatError
    def list(self) -> list[FormatInfo]: ...
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
            raise CyclicImportError(state.cycle(canonical))       # MG006
        if state.depth > MAX_IMPORT_DEPTH:
            raise ImportDepthError(canonical)                     # MG006
        if canonical in state.cache:              # один документ — один раз
            return state.cache[canonical]

        state.visiting.append(canonical)
        state.depth += 1
        try:
            document = self.parser.parse_document(canonical)
            for spec in document.imports:
                resolved = resolve_import(canonical.parent, spec, state)  # MG022
                if spec.kind == "yaml":
                    imported = self._resolve_document(resolved, state)
                    document = merge_documents(document, imported, spec)  # MG002
                else:
                    state.resources[spec.alias] = read_resource(resolved, spec)
            state.cache[canonical] = document
            return document
        finally:
            state.visiting.pop()
            state.depth -= 1
```

- `resolve_import` разрешает путь относительно **файла, где объявлен импорт**, и проверяет project root (MG022).
- `merge_documents` реализует ADR-0001 #1–#5: entities/enums/types объединяются, дубликаты имён → MG002; `model.name/description/metadata` импорта не мержатся.
- Ресурсы (`kind="resource"`) читаются как bytes и складываются в `state.resources`; дубль alias → MG025.
- Один resolved-path обрабатывается один раз; повторный импорт/источник не дублирует сущности (MG024 — Warning).
- `state.resources` попадает в `GenerationContext.imports`.

### 4.3 Entity-level extends

```python
def merge_entity(parent: Entity, child: Entity) -> Entity:
    """ADR-0001 #2–#3: parent-поля на своих позициях, override заменяет
       поле целиком, новые поля child — в конце."""
    if len({f.name for f in child.fields}) != len(child.fields):
        raise DuplicateFieldError(child.name)                    # MG003
    overrides = {f.name: f for f in child.fields}
    fields = tuple(overrides.pop(f.name, f) for f in parent.fields)
    fields += tuple(f for f in child.fields if f.name in overrides)
    return child.model_copy(update={"fields": fields, "extends": None})
```

Разрешение `extends`:

```python
def resolve_extends(entity: Entity, scope: ImportScope, stack: tuple[str, ...]) -> Entity:
    if entity.extends is None:
        return entity
    if entity.name in stack:
        raise ExtendsCycleError(stack + (entity.name,))           # MG009
    if len(stack) > MAX_EXTENDS_DEPTH:
        raise ExtendsDepthError(entity.name)                       # MG009
    parent = scope.resolve(entity.extends)   # short name или {import, entity}; MG009
    parent = resolve_extends(parent, scope, stack + (entity.name,))
    return merge_entity(parent, entity)
```

- `ImportScope` — индекс entity по alias и по имени в import-closure документа.
- Короткое имя допустимо только при уникальном совпадении; иначе MG009.
- `extends` разрешается только внутри closure своего документа; сущность из другого source — MG009.
- Наследуются только `fields`; `description`, `version`, `updated_at`, `metadata` остаются child'а.
- Порядок полей детерминирован.

### 4.4 Validator (semantic, поверх Pydantic)

```python
class DiagnosticLocation(BaseModel):
    file: Path | None = None
    entity: str | None = None
    field: str | None = None
    path: str | None = None          # JSON-path внутри документа

class Diagnostic(BaseModel):
    level: Literal["warning", "error"]
    code: str                        # MG...
    message: str
    location: DiagnosticLocation | None = None

def validate(
    model: SourceModel,
    rules: GeneratorRules,
    *,
    project_root: Path,
    format_plugin: FormatPlugin,
) -> list[Diagnostic]: ...
```

| Code | Проверка | Уровень | Фаза |
|------|----------|---------|------|
| MG000 | YAML syntax / duplicate keys / multi-doc / non-dict | error | parse |
| MG001 | Ссылка type на несуществующий enum/type | error | validate |
| MG002 | Дубликат имени entity/enum/type после композиции | error | composition |
| MG003 | Дубликат поля в entity | error | validate |
| MG004 | Неизвестный тип (не primitive формата, не enum/type) | error | validate |
| MG005 | Некорректный regex в `constraints.pattern` | error | validate |
| MG006 | Циклический import / depth > 10 | error | composition |
| MG007 | `format` отсутствует / неизвестен / смешаны форматы | error | parse |
| MG008 | `version` отсутствует / не поддерживается | error | parse |
| MG009 | `extends` не найден / неоднозначен / цикл / depth > 10 | error | composition |
| MG010 | `nullable=false` + `default=null` | error | validate |
| MG011 | `required=true` + `nullable=true` | warning | validate |
| MG012 | Entity.name не PascalCase | warning | validate |
| MG013 | Неиспользуемый enum/type | warning | validate |
| MG014 | `updated_at` устарела (file-per-entity, opt-in) | warning | validate |
| MG015 | Пустой description у required-поля | warning | validate |
| MG016 | `default` не приводится к итоговому type | error | validate |
| MG017 | `default` нарушает constraints/enum | error | validate |
| MG018 | Неизвестное имя в `input` | error | slice |
| MG019 | Пустой enum / дубликат имени/значения | error | validate |
| MG020 | Цикл `CustomType.base` / depth > 10 | error | validate |
| MG021 | Неприменимый/противоречивый constraint | error | validate |
| MG022 | Импорт вне project root | error | composition |
| MG023 | YAML в `sources` не является документом модели | error | discovery |
| MG024 | Дубликат resolved-пути | warning | discovery |
| MG025 | Дубликат alias `as` | error | composition |
| MG026 | Case-insensitive коллизия имён | warning | validate |
| MG028 | Имя не соответствует pattern | error | Pydantic |
| MG040 | Некорректный artifact path / content | error | write |
| MG041 | Ownership-конфликт / `on_conflict: error` | error | write |
| MG042 | Дубликат artifact path / case-collision | error | planning |
| MG043 | `skip` для не-owned файла: не трогаем и не присваиваем | warning | planning |
| MG050 | Changed owned-файл не удалён при cleanup | warning | cleanup |

- Pydantic-ошибки маппятся в MG028/MG3xx с локацией.
- `format_plugin.validate(document)` вызывается после базовой структурной валидации; его `Diagnostic[]` объединяются с ядровыми.
- `--strict` повышает warning → error с учётом `rules.diagnostics.ignore`.
- Pydantic отвечает за структуру; Validator — за семантику (cross-ref'ы, null-matrix, типы, constraints).
- `validate()` не мутирует модель.

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

    rules_file: Path | None = None         # -c / --config

    debug: bool = False
    verbose: bool = False
    quiet: bool = False
    watch_debounce_ms: int = 300
```

- Приоритет: CLI-флаги → env → `.env` → defaults. Отдельного app-config-файла нет; `.mg.yaml` — это `GeneratorRules`.
- `plugins_dir` и `cache_dir` **удалены**: плагины из директорий с ручным `sys.path` не поддерживаются (§6.3); кэш — future.
- `config_file` переименован в `rules_file`, чтобы не путать с app config.
- CLI собирает `AppConfig` после парсинга аргументов и передаёт override'ы в `Engine`.

### 5.2 GeneratorRulesLoader

```python
class GeneratorRulesLoader:
    def load(self, path: Path) -> GeneratorRules:
        data = load_yaml(path)                  # ruamel.yaml, duplicate keys → error
        try:
            return GeneratorRules.model_validate(data)
        except ValidationError as e:
            raise ConfigValidationError.from_pydantic(e, path) from e

    @classmethod
    def discover(cls, start: Path = Path.cwd()) -> Path | None:
        """Ищет .mg.yaml от start вверх до git-root (или ФС-root)."""
```

- Относительные пути внутри `GeneratorRules` трактуются от `path.parent`.
- `discover()` возвращает путь, а не загруженный объект: Engine должен знать `config_dir`.
- Если конфигов несколько в цепочке — берётся ближайший; это фиксируется в `EngineReport`.
- `version` проверяется (`"1.0"`); неизвестная версия → MG3xx (exit 2).

### 5.3 Логирование (единая точка)

```python
def setup_logging(config: AppConfig) -> None:
    """Вызывается CLI. Библиотека этого не делает."""
    logger = logging.getLogger("mg")
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
    return logging.getLogger(f"mg.{name}")
```

- В библиотеке `setup_logging()` не вызывается; на `mg`-логгере висит `NullHandler`, `propagate` не ломает logging хоста.
- Никакого `logging.basicConfig(force=True)`.
- Логи не попадают на stdout (не ломается `--output-format json`) — только stderr/file.
- Значения `variables`, похожие на секреты, редактируются в логах и `config show`.

---

## 6. Plugin Loader

### 6.1 Entry points

```python
class PluginLoader:
    GROUP_GENERATORS = "metadata_generator.generators"
    GROUP_FORMATS    = "metadata_generator.formats"
    SUPPORTED_API    = frozenset({"1"})

    def discover(self) -> list[PluginInfo]:
        """Загружает классы, но не инстанцирует; ошибки — в PluginInfo, не падают."""

    def get_generator(self, generator_id: str) -> GeneratorPlugin:
        """Ленивая загрузка выбранного генератора; incompatible/import error → exit 2."""

    def load_formats(self) -> list[FormatPlugin]:
        """Нужны для парсинга; конфликт имён — MG007."""
```

- `PluginInfo`: `id`, `name`, `distribution`, `version`, `api_version`, `status` (`ok|incompatible|error`), `error`.
- `ep.load()` может кинуть любое исключение: оно превращается в `PluginLoadError` и показывается в `mg gen list`; **не ломает** запуск, если плагин не выбран.
- `plugin.id != ep.name` → **Error** (не Warning): id — часть контракта.
- Дубликат `id` из разных distribution'ов → **Error** с перечнем distribution'ов; silent overwrite запрещён.
- Несовместимый `api_version`:
  - не выбран — `status="incompatible"` + Warning в списке;
  - выбран (`-g`) или `enabled: true` в конфиге — exit 2.
- `EXPECTED_API_VERSION` — множество поддерживаемых; ошибка содержит distribution, версию плагина и требуемую версию ядра.
- Плагины сортируются по `id` для детерминизма.
- `mg gen list` не инстанцирует плагины; `mg gen info <id>` — инстанцирует.
- Формат-плагины загружаются eagerly (нужны для парсинга), но ошибка одного не должна мешать `mg gen list`; для `generate` достаточно форматов, используемых в sources.

### 6.2 Регистрация (pyproject.toml проекта-плагина)

```toml
[project.entry-points."metadata_generator.generators"]
oracle-ddl = "my_oracle_generator:MyGenerator"

# для новых форматов:
[project.entry-points."metadata_generator.formats"]
sql-model = "my_oracle_generator.format:SqlModelFormat"
```

### 6.3 Локальная разработка плагина

`sys.path`-хаки и `plugins_dir` **не поддерживаются**. Дев-цикл:

```bash
pip install -e ./plugins/my-generator   # editable install
mg gen list                             # плагин виден
```

(Future, v0.3+: `--plugin path/to/module.py` — явный importlib spec loading, без правки sys.path.)

---

## 7. CLI (Typer)

### 7.1 Структура команд

```python
app = typer.Typer(name="mg", help="Metadata Generator", no_args_is_help=True)
app.add_typer(config_app, name="config")   # show, validate
app.add_typer(model_app,  name="model")    # validate, schema (P2)
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
    ignore: Optional[list[str]] = typer.Option(None, "--ignore", help="коды MG..., многократно"),
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
- `--clean` — разовый cleanup текущего запуска; `mg clean` — все манифесты.
- `mg init` не перезаписывает файл без `--force`.
- `mg config show` показывает resolved paths и redact секретов; `--output-format json`.
- `mg model validate` принимает несколько файлов/каталогов; `--output-format json`.

### 7.2 Выходные коды и поведение при ошибках

| Ситуация | exit code |
|----------|-----------|
| Успех | 0 |
| Ошибки парсинга/валидации/генерации, drift `--check`, warnings при `--strict` | 1 |
| Config/usage: нет `.mg.yaml`, неизвестный generator id, `--var` без `=`, `api_version` mismatch, ошибка выбранного плагина, ошибка схемы `.mg.yaml` | 2 |
| Ctrl+C | 130 |

Ошибка одного генератора: логируется, остальные продолжаются (aggregate отчёт в конце).

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

Приоритет: CLI `--var` > `.mg.yaml variables`. Все значения — строки. Результат — `GenerationContext.variables`. Ядро не подставляет vars в пути/шаблоны само — это решение плагина. Секреты не логируются.

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
  "report_version": 1,
  "success": true,
  "exit_code": 0,
  "run_id": "01J...",
  "diagnostics": [
    {"level": "warning", "code": "MG012", "message": "...", "location": {"file": "model.yaml", "entity": "User"}}
  ],
  "generators": [
    {
      "id": "oracle-ddl",
      "status": "ok",
      "duration_ms": 42,
      "artifacts": [
        {"path": "user.sql", "status": "create", "sha256": "..."}
      ]
    }
  ],
  "timings": {"parse_ms": 12, "generate_ms": 55}
}
```

- `EngineReport` — общий результат запуска (не путается с `GenerationResult` одного плагина).
- JSON-отчёт печатается только в stdout; логи — stderr/file.
- `--quiet` подавляет человекочитаемый вывод, но не JSON.
- Порядок `generators`/`artifacts` детерминирован (по id/path).

---

## 8. Artifact Writer

### 8.1 Валидация путей

```python
WIN_RESERVED = {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)} | {"CON", "PRN", "AUX", "NUL"}

def validate_artifact_path(output_dir: Path, artifact: Artifact) -> Path:
    p = PurePosixPath(artifact.path)
    if p.is_absolute() or not p.parts:
        raise ArtifactPathError(MG040, artifact, "path must be relative")
    for part in p.parts:
        stem = part.split(".", 1)[0].upper()
        if (part in {"", ".", ".."} or part.startswith(".mg") or stem in WIN_RESERVED
                or part.endswith((" ", ".")) or "\x00" in part or "\\" in part):
            raise ArtifactPathError(MG040, artifact, "invalid path segment")
    if len(str(p)) > 4096 or any(len(part) > 255 for part in p.parts):
        raise ArtifactPathError(MG040, artifact, "path too long")

    output_resolved = output_dir.resolve()
    target = (output_resolved / p).resolve()
    if not target.is_relative_to(output_resolved):
        raise ArtifactPathError(MG040, artifact, "escapes output_dir")  # '..' / symlink
    return target
```

Дополнительно:

- Путь нормализуется в NFC; внутри одного запуска и в общем `output_dir` проверяются case-insensitive коллизии (MG042).
- Symlink-родитель, ведущий наружу, отклоняется; проверка повторяется непосредственно перед записью.
- `content` проверяется на `str`, UTF-8, LF, отсутствие BOM.
- Дубликаты `path` внутри `GenerationResult` — MG042.

### 8.2 Planning, ownership и on_conflict

До записи Engine строит `ExecutionPlan`:

```python
@dataclass(frozen=True)
class PlannedArtifact:
    generator_id: str
    path: PurePosixPath
    action: Literal["create", "update", "skip", "delete", "conflict"]
    sha256: str

@dataclass
class ExecutionPlan:
    artifacts: list[PlannedArtifact]
    conflicts: list[Diagnostic]
```

- Загружаются манифесты **каждого** генератора из `output_dir/.mg/manifests/<id>.json`.
- `owned` = пути из манифеста этого генератора.
- Если путь уже занят другим генератором в том же запуске/`output_dir` — MG042 до записи.
- `on_conflict`:

| `on_conflict` | Файл существует и owned | Файл существует и не owned |
|---|---|---|
| `overwrite` (default) | перезаписать | **MG041**, только с `--force` |
| `skip` | не трогать, записать в manifest с текущим sha256 | не трогать, **не** добавлять в manifest; Warning MG043 |
| `error` | MG041, генератор не пишет | MG041 |

- `--force` разрешает перезапись не-owned; после записи файл становится owned (попадает в manifest).
- `--check` сравнивает план с диском и манифестом; drift → exit 1.

### 8.3 Manifest

Per-generator manifest: `output_dir/.mg/manifests/<generator-id>.json`.

```json
{
  "manifest_version": 1,
  "generator": "oracle-ddl",
  "mg_version": "0.1.0",
  "plugin_version": "1.2.0",
  "format": {"name": "entity-model", "version": "1.0"},
  "generated_at": "2026-11-11T12:34:56Z",
  "artifacts": [
    {"path": "user.sql", "sha256": "...", "skipped": false}
  ]
}
```

- Пишется после успешной записи артефактов генератора, атомарно (staging → `os.replace`).
- Содержит только артефакты этого генератора.
- `skipped: true` — ядро не писало файл; cleanup такие записи не удаляет.
- `.mg/` рекомендуется в `.gitignore`; манифест не предназначен для коммита.
- `--check` не обновляет манифест.
- Manifest не является источником «владельца» для чужих файлов.

### 8.4 Atomicity и блокировки

```python
with staging_dir(output_dir) as staging:
    write_all(staging, artifacts)          # проверки уже выполнены
    for path in artifacts:
        os.replace(staging / path, output_dir / path)
    write_manifest_atomic(output_dir, manifest)
```

- Staging — внутри `output_dir` (та же ФС), имя `.mg-staging-<pid>-<uuid>`.
- Сначала все проверки конфликтов, потом запись. Ошибка до записи не оставляет файлов.
- Batch-транзакции нет: при аварии посреди `os.replace` возможен частично обновлённый набор; manifest пишется последним, следующий запуск обнаружит drift по sha256.
- Staging удаляется при старте и по сигналу.
- Lock: `.mg/lock` (O_EXCL, PID, timestamp); второй запуск в тот же `output_dir` — exit 2. Stale-lock — предупреждение + `--force-unlock` (P2). `mg clean` берёт тот же lock.
- `--dry-run`/`--plan` не создают каталоги, не берут write-lock и не меняют файлы.

### 8.5 Cleanup

- Cleanup работает **только с owned-артефактами из манифестов**; не сканирует `output_dir` на «неизвестные» файлы.
- Записи с `skipped: true` не удаляются никогда — это файлы, которые ядро не писало.
- Кандидат — запись манифеста (`skipped: false`), которой нет в текущем результате генератора.
- Cleanup в рамках `generate` — только для **успешно завершившихся** генераторов; упавший генератор свой манифест не трогает.
- Удаляется только если текущий sha256 совпадает с manifest; иначе Warning MG050, файл сохраняется.
- `cleanup: off` — default; `prompt` — только tty; `enabled` — удалять неизменённые stale-файлы.
- `mg generate --clean` — разово `enabled`; `mg clean` — все манифесты; вне tty нужен `--yes`.
- Не трогает `.git`, `.mg`, скрытые файлы, каталоги и файлы вне `output_dir`.
- Удалённый из конфига генератор: манифест остаётся, `mg clean` может удалить его неизменённые артефакты.

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

- **Первичная генерация** выполняется сразу при старте `mg watch` (как `mg generate` с теми же флагами).
- **Наблюдаемые пути:** все `sources.path` (файлы и каталоги), импортируемые YAML-модели, `.mg.yaml`, файлы шаблонов, указанные в `options` генераторов (если плагин сообщает их через `watch_paths` — future; v1 наблюдает только модели и конфиг).
- **Игнорируются:** все `output_dir` текущего конфига, `.git`, `.mg`, `__pycache__`, `.venv`, `venv`, `node_modules`, `*.tmp`, `*.swp`, `*~`.
- **Debounce:** изменения батчатся за `watch_debounce_ms` (default 300); на батч выполняется одна генерация.
- **Перезагрузка конфига:** изменение `.mg.yaml` (или `-c`-файла) перезагружает `GeneratorRules`; **плагины не перезагружаются** — для обновления кода плагина нужен перезапуск (сообщается в лог).
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

```
metadata-generator/
├── src/metadata_generator/
│   ├── __init__.py                  # публичный API (см. §2), __all__, py.typed
│   ├── py.typed
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                  # typer app (generate/watch/init/clean) + sub-apps
│   │   ├── config_cmds.py           # mg config show/validate
│   │   ├── model_cmds.py            # mg model validate/schema
│   │   ├── gen_cmds.py              # mg gen list/info
│   │   ├── format_cmds.py           # mg format list
│   │   └── formatters.py            # TextFormatter, JsonFormatter
│   ├── core/
│   │   ├── __init__.py
│   │   ├── document.py              # ModelDocument, ImportSpec
│   │   ├── model.py                 # SourceModel, ModelSlice, Entity, FieldDef, EnumDef, CustomType
│   │   ├── parser.py                # Parser (ruamel.yaml), header, imports
│   │   ├── composition.py           # imports/extends, merge (ADR-0001), closure
│   │   ├── validator.py             # semantic валидация (Diagnostic)
│   │   └── naming.py                # NamingStyle, transform()
│   ├── config/
│   │   ├── __init__.py
│   │   ├── app_config.py            # AppConfig
│   │   ├── generator_rules.py       # GeneratorRules, GeneratorRulesLoader
│   │   └── logging.py               # setup_logging(), get_logger() — ЕДИНСТВЕННАЯ точка
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── engine.py                # Engine orchestration + public Engine facade
│   │   ├── planning.py              # ExecutionPlan: create/update/skip/delete/conflict
│   │   ├── locking.py               # .mg/lock (O_EXCL, PID, stale)
│   │   ├── plugin_loader.py         # PluginLoader (generators + formats)
│   │   ├── format_registry.py       # FormatRegistry
│   │   └── artifact_writer.py       # validate paths, ownership, atomic write, manifest, cleanup
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── generator.py             # GeneratorPlugin, GeneratorInput, GenerationContext, Artifact
│   │   ├── formats.py               # FormatPlugin, EntityModelFormat
│   │   └── diagnostics.py           # Diagnostic, DiagnosticLocation
│   ├── watch/
│   │   ├── __init__.py
│   │   ├── watcher.py               # Watcher (lazy watchdog), DebounceHandler
│   │   └── cache.py                 # CacheStrategy (future)
│   ├── templating.py                # optional Jinja2 helper (extra [jinja])
│   └── utils/
│       ├── __init__.py
│       ├── yaml.py                  # load_yaml() поверх ruamel.yaml
│       └── exceptions.py            # ConfigValidationError, CyclicImportError, ...
├── examples/                        # reference-плагин + примеры моделей/конфигов
│   ├── reference-generator/
│   ├── reference-format/
│   └── models/
├── tests/
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_composition.py      # каждый пункт ADR-0001
│   │   ├── test_validator.py
│   │   ├── test_config.py
│   │   ├── test_planning.py
│   │   ├── test_artifact_writer.py
│   │   └── test_naming.py
│   ├── property/
│   │   ├── test_parser.py           # hypothesis: мусор + round-trip
│   │   └── test_validator.py        # валидные/невалидные стратегии
│   ├── integration/
│   │   ├── test_generate.py
│   │   ├── test_cleanup.py
│   │   └── test_cli.py
│   ├── contract/
│   │   ├── test_generator_contract.py
│   │   └── test_format_contract.py
│   ├── security/
│   │   ├── test_paths.py
│   │   ├── test_symlinks.py
│   │   └── test_imports.py
│   ├── golden/
│   │   ├── fixtures/models/
│   │   ├── fixtures/expected/
│   │   └── test_golden.py
│   └── conftest.py
├── docs/
│   ├── requirements/                # ТЗ (index, v1.0, v1.1, v1.2, v1.3)
│   ├── system-design/
│   ├── reviews/
│   ├── adr/                         # 0001-composition-merge-semantics.md
│   └── reference/                   # diagnostics.md (при реализации)
├── tools/
│   ├── check_docs.py                # проверка документации
│   └── check_wheel.py               # проверка wheel/sdist + smoke-install
├── .github/workflows/               # docs, ci, release
├── pyproject.toml
├── pyrightconfig.json               # basedpyright/Pyright: src-layout, extraPaths, .venv
├── uv.lock
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

---

## 11. Тестирование (охват v1.3)

### 11.1 Приоритеты

1. **Golden-file**: fixtures → expected artifacts (главная защита от регрессии артефактов). Так как встроенных генераторов нет, golden-тесты используют **reference-плагин** из `examples/`.
2. Merge-семантика ADR-0001 — тест на каждое правило (1–16 из таблицы решений).
3. **Null-matrix** — все 12 комбинаций из ТЗ §3.6, включая `UNSET` vs explicit `null`.
4. Parser: simple / imports / entity.extends / cycle / depth / unknown format / unknown version / duplicate keys / YAML 1.2-скаляры.
5. Integration CLI: полный цикл, exit codes, `--strict`, `--var`, `--dry-run`/`--plan`/`--check`, `--include-disabled`.
6. **Contract-тесты plugin API**: reference-generator и reference-format проходят публичный контракт; несовместимый `api_version` ведёт себя по §6.
7. **Security**: path traversal, symlink-выход из `output_dir`, импорт вне project root, duplicate keys, YAML-алиасы (billion laughs), секреты в логах.
8. **Cleanup**: modified owned-файл не удаляется (MG050), чужой файл не удаляется, shared `output_dir`, удалённый из конфига генератор.
9. **Concurrency**: второй запуск при held lock; stale lock.
10. **Determinism**: повторный запуск даёт идентичные байты; порядок source/artifact/plugin стабилен; артефакты не содержат абсолютных путей.

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
- Отдельно проверяется lazy-import: `mg --help` не должен импортировать `watchdog`.

---

## 12. Зависимости (pyproject.toml)

```toml
[project]
name = "metadata-generator"
version = "0.1.0"
description = "CLI tool and library for metadata-driven code generation"
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.11"
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Typing :: Typed",
]
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "ruamel.yaml>=0.18.6",
    "rich>=13.7.0",
]

[project.optional-dependencies]
watch = ["watchdog>=4.0.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.100.0",
    "ruff>=0.4.0",
    "pyrefly>=1.4.0",
]

[project.scripts]
mg = "metadata_generator.cli.main:app"

[project.urls]
Homepage = "https://github.com/<org>/metadata-generator"
Documentation = "https://github.com/<org>/metadata-generator/tree/main/docs"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
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
  Для установки пакета пользователями остаётся `pip install metadata-generator`.
- Сборка проверяется `tools/check_wheel.py`: wheel содержит `py.typed` и LICENSE, метаданные
  зависимостей корректны, sdist не содержит dev-harness; выполняется smoke-install в чистом venv.
- Команда `mg` определена в `[project.scripts]` и проверяется при сборке wheel.
- `watchdog` — **optional extra** `[watch]`, lazy-import в `watch/watcher.py`; без `mg watch` пакет не требуется.
- `ruamel.yaml` (YAML 1.2) вместо PyYAML: duplicate keys → ошибка, корректные `yes/no`, даты.
- Пакет поставляет `py.typed` (PEP 561); публичный API — `__all__` в `__init__.py`.
- Python 3.11+ — ради `StrEnum`, `Self`, `tomllib`, современных Pydantic v2; 3.11/3.12 в CI-матрице.
- Встроенных генераторов и `[project.entry-points]` в ядре нет: entry points регистрируют плагины.

---

## 13. Проектировочные решения (v1.3, сводка)

| Решение | Причина | Где |
|---------|---------|-----|
| Явные `ModelDocument` → `SourceModel` → `ModelSlice` | Разная ответственность и гарантии на каждом этапе | ТЗ §3.1, §2.1 |
| Заголовок документа: `format` + `version` обязательны; `metadata` — extension point | Наследование формата — зона формат-плагина; нет двойного extends | ТЗ §3.4 |
| Один запуск — один формат | Упрощает реестр, парсер и контекст генератора | ТЗ §3.4 |
| `UNSET` отличается от `default: null` | Null-matrix должна различать «не задан» и «null» | ТЗ §3.6, §3.1 |
| Сущности изолированы (без relations в базе) | Нейтральность ядра | ТЗ §1.1 |
| Два типа плагинов (generators, formats) | Реестр форматов расширяем | §6 |
| Вход генератора — замкнутый срез (`ModelSlice`) | Cross-entity артефакты + корректные ссылки на enums/types | ТЗ §5 |
| App-config плагину не передаётся | Чистый публичный контракт | §2.1 |
| Имена файлов задаёт плагин, ядро валидирует пути | Нет двух источников имён | §8.1 |
| `naming_convention` — подсказка в context | Не переименовывать модель молча | §2.6 |
| Плагин `api_version` через `ClassVar` | Обратная совместимость контракта | §6.1 |
| Ownership + per-generator manifest | Безопасная перезапись и cleanup в общем `output_dir` | §8.2–8.3 |
| `cleanup: off` по умолчанию, удаление только unchanged owned-файлов | Защита пользовательских файлов | §8.5 |
| Atomic write + staging + lock | Безопасная запись и защита от параллельных запусков | §8.4 |
| `--plan`/`--check` без побочных эффектов | CI и предсказуемость | §7.1 |
| `ruamel.yaml`, YAML 1.2, duplicate keys → error | Однозначность и отсутствие «тихих» потерь | §4.1 |
| Локальные плагины через pip -e, не sys.path | Стандарт, без хаков | §6.3 |
| Логи в stderr/file, CLI-вывод в stdout (rich) | Совместимость с `--output-format json` | §5.3 |
| `Engine` как библиотечный фасад без `sys.exit`/root-logger | First-class библиотечное использование | §2.8 |
