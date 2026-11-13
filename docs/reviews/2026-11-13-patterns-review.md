# Patterns & Antipatterns Review — 2026-11-13

**Область:** `src/eggpipe`, `examples/*/src`, тесты — read-only ревью.
**Фокус:** паттерны проектирования, ООП-границы, антипаттерны Python-кода.
**Основание:** skill `clean-code`, ТЗ v2.0, System Design, ADR-0001/0008.

## Резюме

Архитектура в целом здоровая: core не зависит от CLI/engine, доменные модели immutable,
плагины отделены контрактами, отчёты и диагностики структурированы. Главная проблема —
не «плохие классы», а **низкоуровневая обработка данных там, где просится доменная операция**.
Из-за этого появляются циклы по `dict` с `continue`, булевы out-параметры `added/changed`,
длинные списки параметров и функции-обёртки, которые ничего не добавляют, кроме перевыброса
исключения.

| Категория | Оценка |
|-----------|--------|
| Доменные модели и value objects | хорошая основа, но есть primitive obsession (`(generator, output_dir)`, пути) |
| Стратегии и полиморфизм | почти не используются: merge и cleanup зашиты в `if` |
| Границы исключений | местами размыты: wrapper-функции только перевыбрасывают |
| Дублирование | есть структурное дублирование (`_merge_enums`/`_merge_types`, CLI-команды) |
| Читаемость | средняя: длинные функции и параметры-«мешки» |
| Тестируемость | высокая, тесты быстрые и поведенческие |

Blocker-находок нет. Основные улучшения — Major/Minor, их стоит делать перед E9 и
следующими крупными изменениями.

## 1. `_merge_metadata`: data munging вместо доменной операции

**Где:** `src/eggpipe/core/layers.py:318-346`.

Сейчас функция — цикл по словарю с четырьмя ветками, три из которых завершаются `continue`:

```python
if key not in result: ...
continue
if isinstance(current, dict) and isinstance(value, dict): ...
continue
if isinstance(current, list) and isinstance(value, list): ...
continue
if current != value: raise ...
```

**Антипаттерн:** «loop-and-continue data munging». Код одновременно знает про структуру
metadata, про стратегию merge, про конфликт и про provenance. Добавление нового типа
(например, tuple или set) потребует ещё одной ветки `continue`. Тестировать отдельные
правила можно только через публичную функцию.

**Паттерны, которые подходят:**

1. **Value Object результата** — `MergeChange(value, changed)` вместо `tuple[..., bool]`.
2. **Диспетчеризация по типу** — `match` или `functools.singledispatch` вместо цепочки
   `isinstance/continue`.
3. **Strategy** — когда политика merge должна быть расширяемой (`KEYED`/`APPEND`/`UNION`/`ERROR`).

Вариант без преждевременной иерархии классов:

```python
@dataclass(frozen=True)
class MergeChange:
    value: Any
    changed: bool = False


@dataclass(frozen=True)
class MergeContext:
    source: Path
    path: str = "metadata"


def merge_metadata(base: dict[str, Any], delta: dict[str, Any], source: Path) -> MergeChange:
    result = dict(base)
    changed = False
    for key, value in delta.items():
        change = merge_value(result.get(key, _MISSING), value, context.with_key(key))
        if change.changed:
            result[key] = change.value
            changed = True
    return MergeChange(result, changed)


def merge_value(current: object, incoming: object, ctx: MergeContext) -> MergeChange:
    match current, incoming:
        case _Missing(), value:
            return MergeChange(value, True)
        case dict(), dict():
            return merge_metadata(current, incoming, ctx.source)
        case list(), list():
            return MergeChange([*current, *incoming], bool(incoming))
        case _ if current == incoming:
            return MergeChange(current)
        case _:
            raise DocumentError("MG029", ctx.source, f"конфликт {ctx.path}")
```

Если политики должны быть расширяемыми, вместо `match` добавляется реестр стратегий:

```python
class MergeStrategy(Protocol):
    def merge(self, current: object, incoming: object, ctx: MergeContext) -> MergeChange: ...

STRATEGIES: dict[MergePolicy, MergeStrategy] = {
    MergePolicy.KEYED: KeyedMerge(),
    MergePolicy.APPEND: AppendMerge(),
    MergePolicy.UNION: UnionMerge(),
    MergePolicy.ERROR: ErrorMerge(),
}
```

Важно: **не превращать это в глубокую иерархию классов**. Для трёх типов достаточно
функций/`singledispatch`; Strategy нужен, когда политика приходит из схемы формата.

**То же касается `_merge_enums` и `_merge_types`** (`layers.py:278-316`). Это почти
копипаста. Лучше один generic helper:

```python
T = TypeVar("T", bound=BaseModel)

def merge_append(base: list[T], delta: Iterable[T], source: Path, label: str) -> MergeChange:
    by_name = {item.name: item for item in base}
    result = list(base)
    for item in delta:
        existing = by_name.get(item.name)
        if existing is None:
            result.append(item)
            by_name[item.name] = item
            continue
        if existing != item:
            raise DocumentError("MG029", source, f"переопределение {label} {item.name} запрещено")
    return MergeChange(result, len(result) != len(base))
```

Это уже убирает дублирование и оставляет одну точку изменения правил `APPEND`.

## 2. `_render_pydantic`: обёртка, которая только перевыбрасывает исключение

**Где:** `examples/tpc-h-generator/src/tpch_generator/generator.py:36-55`.

```python
def _render_pydantic(...):
    try:
        return render_pydantic(...)
    except (TemplateError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
```

**Антипаттерн:** «exception laundering wrapper». Функция не добавляет контекст, не меняет
тип на доменный, не логирует — только ловит и выбрасывает почти то же самое. То же самое
делает `_render_ddl`. Это лишний уровень, который скрывает реальный источник ошибки и
создаёт иллюзию абстракции.

**Предпочтение:**

- удалить обе обёртки и вызывать `render_ddl`/`render_pydantic` напрямую;
- если нужен доменный тип, конвертировать **один раз на границе генератора**:

```python
class TpchGenerationError(Exception):
    """Ошибка подготовки TPC-H артефактов."""


def _render(model, config, context) -> list[Artifact]:
    try:
        return [...]
    except (TemplateError, ValueError) as exc:
        raise TpchGenerationError("не удалось подготовить TPC-H артефакты") from exc
```

Или вообще положиться на engine: он уже превращает исключение плагина в MG300.
Правило: **обёртка оправдана, только если она добавляет смысл** — контекст, доменный тип,
retry, cleanup, диагностику.

## 3. Сквозные находки

### Major

| # | Антипаттерн | Где | Предпочтение |
|---|-------------|-----|--------------|
| P1 | Низкоуровневый цикл + `continue` для metadata/enums/types | `layers.py:278-346` | `MergeChange` + `match`/`singledispatch`; generic append |
| P2 | Обёртки, только перевыбрасывающие исключение | `tpch_generator/generator.py:36-55` | удалить или один boundary-translator |
| P3 | Длинные списки параметров и параметры-«мешки» | `cli/main.py:181` (17), `:243` (19), `:363` (16), `discovery.py:411` (8) | `RunOptions`, `ResourceCollector`, `ReportContext` |
| P4 | Primitive obsession для location/path | `artifact_writer.py`, `engine.py`, `manifest` | `LocationKey(generator, output_dir)`, `ArtifactPath` |
| P5 | Дублирование политики ignore/strict | `engine.py:_filter_ignored`, `cli/main.py:_print_report` | `DiagnosticPolicy` с методами `filter`/`promote` |
| P6 | Ручная валидация metadata через `Any` и десятки `isinstance` | `examples/tpc-h-generator/src/tpch_generator/metadata.py:23-69` | Pydantic-модели `PostgresField`/`PostgresTable` |
| P7 | Булевы out-параметры `added/changed` | `layers.py` | `MergeChange`/`MergeResult` value object |
| P8 | Копипаста `_merge_enums`/`_merge_types` | `layers.py:278-316` | generic `merge_append` |

### Minor

| # | Антипаттерн | Где | Предпочтение |
|---|-------------|-----|--------------|
| P9 | `_MISSING`-sentinel там, где язык умеет required keyword | `interfaces/generator.py:generator` | `input_formats` без default |
| P10 | Вложенный `Handler` и `run_once`-замыкание в watch | `watch/watcher.py:28-92`, `cli/main.py:363` | `WatchHandler`/`WatchRunner` с явными зависимостями |
| P11 | Изменяемый «мешок» результата `_GeneratorRun` | `engine.py:57-63` | frozen dataclass с tuple-полями |
| P12 | Дублирование `error`/`warning` фабрик | `interfaces/diagnostics.py:33-64` | `Diagnostic.error()` / `Diagnostic.warning()` или один factory |
| P13 | `getattr`-проверки контракта формата | `format_registry.py:104-135` | один `validate_contract` + `Protocol`/`TypeGuard` |
| P14 | CLI-команды дублируют одинаковые `try/except` | `cli/main.py:288-294`, `447-493`, `547-578` | один декоратор `@command_errors` |
| P15 | «Сериализовать в dict, чтобы провалидировать» | `layers.py:_validate_entity` (`entity.model_dump()`) | `model_validate(entity, from_attributes=True)` |

## 4. Карта паттернов для проекта

| Паттерн | Где уместен | Не уместен |
|---------|-------------|------------|
| **Value Object** | `LocationKey`, `MergeChange`, `ArtifactPath`, `RunOptions` | там, где достаточно одного поля |
| **Strategy / Registry** | merge policies, cleanup policies, future format rules | если реализация одна и нет планов расширять |
| **Policy Object** | ignore/strict, exit code, cleanup decision | если политика меняется одним `if` |
| **Builder** | `EngineReport`, `ResourceCollector`, `PlanBuilder` | для 2–3 полей |
| **Adapter** | `@generator`, plugin loader | для простой функции без адаптации |
| **Chain / Resolver** | `FormatRegistry.accepts`, import resolution | если цепочка фиксированной длины 1–2 |
| **Factory** | `Diagnostic.error/warning`, `PlanDecision` | для одного конструктора |
| **Template Method** | `FormatPlugin.parse/validate` hooks | для независимых операций |

**Правило выбора:** сначала функция + `dataclass` + `Protocol`; класс/иерархия — только
когда есть **изменяемая политика**, **несколько реализаций** или **состояние между шагами**.
ООП ради ООП здесь вредно: Python хорошо выражает стратегии через `Protocol` и
`singledispatch`.

## 5. Что не надо менять

- Не оборачивать каждую функцию в класс «на будущее».
- Не заменять `UNSET` на `None` — это осмысленный sentinel.
- Не строить иерархию `MergeStrategy` из одного класса; начать с функций и выделить
  Strategy, когда появится schema-driven policy.
- Не прятать простые `dataclass`/Pydantic-модели за геттерами/сеттерами.
- Не превращать `Diagnostic` в исключение: это DTO для отчёта.

## 6. План

1. **P1 + P7 + P8** — `MergeChange`, generic append, один metadata merge. Это уменьшит
   ветвление и дублирование в `layers.py`, не меняя поведения.
2. **P2** — удалить `_render_ddl`/`_render_pydantic`; оставить один boundary translator
   только если нужен доменный тип.
3. **P3 + P4** — `RunOptions` для CLI, `LocationKey` для manifest/ownership.
4. **P5** — `DiagnosticPolicy` для ignore/strict и exit code.
5. **P6** — Pydantic-модели для `metadata.postgres` в example.
6. **P9–P15** — по мере касания файлов, отдельными PR.

## 7. Обновление skills

- В `clean-code` добавлена ссылка на новый skill.
- Новый skill `python-patterns` содержит каталог паттернов, антипаттернов и решающее
  дерево «функция → value object → Protocol → Strategy → иерархия».
- В `python-patterns` зафиксированы два разобранных случая как эталонные примеры:
  `_merge_metadata` и wrapper-функции.

## 8. Проверенные файлы

`src/eggpipe`: `__init__.py`, `cli/main.py`, `config/*`, `core/*`, `engine/*`,
`interfaces/*`, `utils/*`, `watch/watcher.py`, `templating.py`;
`examples`: `reference-generator`, `tpc-h-generator` (src);
`tests`: выборочно, как потребитель паттернов.
