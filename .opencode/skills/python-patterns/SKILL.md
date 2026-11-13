---
name: python-patterns
description: Паттерны и антипаттерны Python для Eggpipe — value objects, strategy, policy, границы исключений
---

# Паттерны и антипаттерны Python

Используй этот skill при ревью, проектировании и рефакторинге кода Eggpipe. Он дополняет
`clean-code`: `clean-code` отвечает за читаемость, этот — за выбор модели/паттерна.

## Главный принцип

Сначала **доменная операция**, потом структура данных. Если функция перебирает `dict`/
`list` с `continue` и знает про типы значений — скорее всего, не хватает value object,
стратегии или диспетчеризации по типу.

Порядок выбора:

```text
функция + dataclass → value object → Protocol → Strategy/Registry → иерархия классов
```

Иерархия уместна только при нескольких реализациях, общей политике или состоянии между
шагами. Не строить класс «на будущее».

## Паттерны

### 1. Value Object

Заменяет tuple/primitive-«ключи» и булевы out-параметры.

```python
@dataclass(frozen=True)
class LocationKey:
    generator: str
    output_dir: str

@dataclass(frozen=True)
class MergeChange:
    value: Any
    changed: bool = False
```

Признаки: `(generator, output_dir)`, `(value, bool)`, `dict[str, Any]` как структура.

### 2. Result / Decision Object

Возвращай не `(value, changed)` и не `(value, diagnostics)`, а объект:

```python
@dataclass(frozen=True)
class MergeChange:
    value: object
    changed: bool
```

Для плана записи: `PlanDecision(action, reason)`, а не набор флагов.

### 3. Strategy / Registry

Когда поведение выбирается по политике (`MergePolicy`) или типу:

```python
class MergeStrategy(Protocol):
    def merge(self, current, incoming, ctx) -> MergeChange: ...

STRATEGIES = {
    MergePolicy.KEYED: KeyedMerge(),
    MergePolicy.APPEND: AppendMerge(),
    MergePolicy.UNION: UnionMerge(),
    MergePolicy.ERROR: ErrorMerge(),
}
```

Начинай с `match`/`functools.singledispatch`; Strategy — когда политика приходит из
конфигурации/схемы формата.

### 4. Policy Object

Правила `ignore`/`strict`/exit code не должны быть размазаны по CLI и Engine:

```python
@dataclass(frozen=True)
class DiagnosticPolicy:
    ignore: frozenset[str]
    strict: bool

    def apply(self, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
        ...
```

### 5. Builder / Collector

Когда функция принимает 6+ параметров и постепенно собирает результат:

```python
@dataclass
class ResourceCollector:
    base: Path
    boundary: Path
    prefix: str | None
    allow_outside: bool
    result: DiscoveredSources

    def collect(self, resources: tuple[ResourceConfig, ...]) -> None: ...
```

### 6. Adapter

`@generator` — правильный адаптер функции к `GeneratorPlugin`. Не дублируй его вручную.
Адаптер оправдан, если выравнивает несовместимые контракты; обёртка «try/except → re-raise»
адаптером не является.

### 7. Chain / Resolver

`FormatRegistry.accepts` — цепочка `extends`. Импорт-резолвер тоже цепочка: путь → alias →
closure. Выноси состояние цепочки в объект (`ResolveState`), а не в 6 параметров.

### 8. Boundary Translator

Исключения переводи один раз на границе слоя:

```python
try:
    artifacts = render(...)
except (TemplateError, ValueError) as exc:
    raise GenerationError("не удалось подготовить артефакты") from exc
```

Внутри слоя не оборачивай исключение, если не добавляешь контекст/тип/cleanup.

## Антипаттерны

### A1. Loop-and-continue data munging

```python
for key, value in delta.items():
    if key not in result:
        ...
        continue
    if isinstance(current, dict) and isinstance(value, dict):
        ...
        continue
    if isinstance(current, list) and isinstance(value, list):
        ...
        continue
    if current != value:
        raise ...
```

Проблема: функция знает про структуру, правила, конфликты и типы одновременно.
Лечение: `MergeChange` + `merge_value` с `match`/`singledispatch`; правила — в стратегиях.

### A2. Exception laundering wrapper

```python
def _render_pydantic(...):
    try:
        return render_pydantic(...)
    except (TemplateError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
```

Проблема: не добавляет смысла, скрывает источник, создаёт ложную абстракцию.
Лечение: удалить; если нужен доменный тип — один translator на границе.

### A3. Boolean out-parameters

`tuple[Value, bool]` и флаги `added/changed` заражают вызывающий код. Лечение:
`MergeChange`/`MergeResult`.

### A4. Primitive obsession

`(generator, output_dir)` как tuple, пути как строки, формат как голый `str`.
Лечение: `LocationKey`, `ArtifactPath`, `FormatInfo`.

### A5. Parameter bag

`_run_engine(... 17 параметров ...)`, `_add_resource(... 8 ...)`.
Лечение: `RunOptions`, `ResourceCollector`, `ReportContext`.

### A6. Copy-paste twins

`_merge_enums` и `_merge_types` почти идентичны. Лечение: generic `merge_append[T]`.

### A7. Hidden mutable state

`_GeneratorRun` как mutable bag, скрытые `self._composition` (исправлено).
Лечение: frozen result-объект или явная передача зависимости.

### A8. Silent broad catch

`except Exception: continue` без диагностики запрещён. На границе плагина допустим
`except Exception` **с** `PluginIssue`/логом.

### A9. Sentinel вместо required keyword

```python
input_formats: set[str] | None | object = _MISSING
```

Если omission — ошибка, достаточно required keyword без default:

```python
def generator(*, input_formats: set[str] | None, ...): ...
```

`UNSET` — другое: это значение домена, а не признак отсутствия аргумента.

### A10. Manual schema validation на `Any`

Десятки `isinstance` в `metadata.py` — признак отсутствующей Pydantic-модели.
Лечение: `PostgresField`/`PostgresTable` + `model_validate`/`TypeAdapter`.

### A11. Обёртка-класс без состояния/политики

Класс с одним методом, который просто вызывает функцию, не нужен. Функция + Protocol
достаточно.

### A12. `getattr`-контракт

Многократные `getattr(plugin, "attr", default)` размазывают контракт. Лечение:
один `validate_contract(plugin)` в загрузчике; дальше код доверяет контракту.

## Когда ООП уместно

- есть несколько реализаций политики (`KEYED/APPEND/UNION/ERROR`);
- нужно состояние между шагами (`ResourceCollector`, `ImportResolver`);
- есть общий шаблон с хуками (`FormatPlugin.parse/validate`);
- нужно инкапсулировать инвариант (`MergeChange`, `LocationKey`).

## Когда ООП вредно

- один класс/один метод без состояния;
- «на будущее»;
- замена простого `dataclass` геттерами;
- иерархия наследования вместо композиции/Protocol;
- wrapper только ради `try/except`.

## Чек-лист

- [ ] Нет цикла по `dict` с 3+ `continue` без доменной операции.
- [ ] Нет `(value, bool)` и флагов `added/changed` на границе функций.
- [ ] Нет обёрток, которые только перевыбрасывают исключение.
- [ ] Нет 6+ параметров без объекта параметров.
- [ ] Ключи/локации/пути — value objects, а не tuple/str.
- [ ] Политики (ignore/strict/cleanup) — объекты, а не копии `if` в CLI и Engine.
- [ ] Контракт плагина проверяется один раз, а не `getattr` в каждом вызове.
- [ ] `except Exception` только на границе, с диагностикой.
- [ ] Нет копипасты near-identical функций.
- [ ] Нет класса без состояния, если хватает функции.

## Формат отчёта

Для каждой находки:

- **Severity:** `Major`/`Minor`/`Nit`.
- **Где:** `path:line`.
- **Антипаттерн:** название из этого skill.
- **Почему плохо:** связь, тестируемость, расширяемость.
- **Паттерн:** конкретное лечение и минимальный рефакторинг.
- **Риск:** что может сломаться.

Не меняй код в рамках read-only ревью без отдельного разрешения.
