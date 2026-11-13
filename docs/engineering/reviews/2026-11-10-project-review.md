# Ревью проекта metadata-generator

- **Дата:** 2026-11-10
- **Объект ревью:** README, ТЗ v1.1, System Design 1.1, ADR-0001, `.session-context.md`
- **Состояние проекта:** только документация, кода ещё нет
- **Цель ревью:** найти противоречия и пробелы до начала разработки ядра v0.1
- **Статус:** P0-находки внесены в [ТЗ v1.2](../requirements/v1.2.md) и обновлённый [System Design](../system-design/index.md) (2026-11-11). P1/P2 остаются backlog'ом.

---

## 1. Краткий вывод

Документация зрелая: есть разделение требований и дизайна, ADR, версионирование, roadmap и продуманная plugin-архитектура. Основные архитектурные идеи (изолированные сущности, плагинные генераторы и форматы, композиция по ADR, атомарная запись) состоятельны.

Но перед разработкой нужно закрыть несколько **блокирующих противоречий**. Они не косметические: часть из них приведёт к неверной реализации контрактов, часть — к опасному поведению при записи файлов.

Главные риски:

1. Null-семантика внутренне противоречива, а `default: null` невозможно отличить от «default не задан».
2. Модель жизненного цикла `SourceModel` не сходится: один и тот же тип используется для документа, композиции и среза, при этом `imports` в нём отсутствует.
3. Схема `.mg.yaml` в ТЗ и System Design различается.
4. `entity.extends` не имеет однозначного синтаксиса и алгоритма разрешения.
5. Срез модели не гарантирует целостность ссылок на enums/types.
6. Механизм расширения форматов не позволяет добавить поля и типы, а генератор не получает формат/версию документа.
7. Манифест и cleanup небезопасны при нескольких генераторах в одном `output_dir`.
8. Публичный API библиотеки в README не совпадает с публичным API в ТЗ/System Design.
9. PyYAML — это YAML 1.1, а не 1.2; это влияет на значения `default`, `version` и имена.
10. Внутренняя модель `Field` конфликтует с `pydantic.Field`.

Ниже — конкретные предложения. Приоритет: **P0** — исправить до v0.1, **P1** — до v0.2, **P2** — можно позже.

---

## 2. Блокирующие проблемы (P0)

### P0-1. Null-матрица противоречит определениям и дефолтам

**Где:** ТЗ §3.1, §3.6; System Design §3.1.

**Проблемы:**

- `required` определён как «значение обязательно при создании», но в таблице валидных состояний есть строка `required=true, default=✓` — «обязательное, но может не указываться при создании». Это противоречие.
- Комбинация `required=false, nullable=false, default=отсутствует` объявлена **Error** с обоснованием «поле невозможно ни пропустить, ни заполнить». Обоснование неверно: поле можно заполнить, нельзя только пропустить. Для SQL это обычная `NOT NULL`-колонка без default.
- Дефолты `required=false`, `nullable=false`, `default=null` сами образуют запрещённую комбинацию. То есть пустое описание поля `- {name: x, type: string}` всегда невалидно. Это ловушка для пользователя.
- `default: null` и «default не задан» представлены одним значением `None`. Проверки `required=true, default=null` и `required=true, default отсутствует` неразличимы.
- Фраза «nullable и constraints касаются поля, не типа» противоречит наличию `constraints` у `CustomType`.

**Предложение:**

1. Ввести явный sentinel `UNSET` (или использовать `model_fields_set`) для `default`. В публичной схеме оставить `null` как допустимое явное значение.
2. Разделить смыслы:
   - `required` — наличие значения **после применения default**;
   - `nullable` — допустимость `null` в значении;
   - `default` — подстановка при отсутствии.
3. Заменить Error для `required=false, nullable=false, no default` на **Warning** (или перенести в format-плагин). Формат-нейтральное ядро не должно решать, допустима ли колонка без default.
4. Привести полную таблицу всех 8 комбинаций `required × nullable × default`, а не 4 строки.
5. Убрать `required_by_default` из `.mg.yaml`, если он не меняет разбор: после Pydantic невозможно отличить «поле не указано» от `false`. Либо реализовать его через `model_fields_set` и описать.
6. Переформулировать фразу про constraints: `nullable` — всегда на поле; constraints могут быть и на типе, и на поле, с явным правилом слияния.

---

### P0-2. `SourceModel` смешивает три разные сущности

**Где:** ТЗ §3.1, §3.5; System Design §3.1, §4.1, §4.2.

**Проблемы:**

- `SourceModel` одновременно означает: документ модели, результат композиции и срез для генератора.
- В ТЗ `imports` лежит в `model`, но в `SourceModel` из System Design поля `imports` нет. При этом код композиции обращается к `doc.model.imports`.
- `Parser.parse_document()` в System Design возвращает `RawDocument`, а `FormatPlugin.parse()` — `SourceModel`; `RawDocument` нигде не определён.
- `SourceModel.name` обязателен, но в примерах импортируемых документов `model.name` отсутствует.
- Не описано, что происходит с `model.name`/`description`/`metadata` при объединении нескольких `sources`.

**Предложение:**

Ввести три явных типа:

```python
class ModelDocument(BaseModel):
    format: str
    version: str
    path: Path
    imports: list[ImportSpec]
    model: SourceModel
    metadata: dict[str, Any]

class SourceModel(BaseModel):   # документ или результат композиции
    name: str | None
    description: str | None
    entities: list[Entity]
    enums: list[Enum]
    types: list[CustomType]

class ModelSlice(BaseModel):    # срез для генератора
    entities: list[Entity]
    enums: list[Enum]
    types: list[CustomType]
```

- `Parser.parse_document() -> ModelDocument`.
- `Composition.resolve() -> SourceModel`.
- `Engine.slice() -> ModelSlice`.
- `GeneratorInput.model: ModelSlice`.
- Явно описать merge `name`/`description`/`metadata` (предлагаю: побеждает корневой документ, метаданные импортов не мержатся).

---

### P0-3. Схема `sources` в ТЗ и System Design разная

**Где:** ТЗ §5 (пример), System Design §3.2.

**Проблема:**

- ТЗ: `sources: - path: ...; entities: []; enums: []; types: []` — фильтры лежат прямо в source.
- System Design: `SourceConfig(path, input: InputSlice)` — фильтры вложены в `input`.

Одна из схем неверна, а примеры и код будут расходиться.

**Предложение:** выбрать одну форму. Рекомендую вложенную `input` — она совпадает с `generators[].input` и проще для расширения. Обновить §5 ТЗ и все примеры.

---

### P0-4. `entity.extends` не определён однозначно

**Где:** ТЗ §3.1, §3.5.4; ADR-0001 §3, §4.

**Проблемы:**

- `extends: ./audit-fields` — это путь к файлу, имя импорта, имя сущности или путь + имя сущности? В примерах встречаются `./shared/audit-fields.yaml` и `./shared/audit`.
- Если импортированный файл содержит несколько сущностей, какая из них родитель?
- Разрешена ли цепочка `A extends B extends C`? Циклы? Глубина?
- Может ли сущность из source A наследовать сущность из source B, если B не импортирован в A?
- Что наследуется кроме `fields`: `description`, `version`, `updated_at`, `metadata`? ADR говорит «только fields», но это стоит продублировать в ТЗ.

**Предложение:**

Ввести явный синтаксис, например:

```yaml
extends:
  import: audit-fields   # имя YAML-импорта (обязательно alias)
  entity: AuditFields
```

или короткую форму `extends: AuditFields`, разрешённую только при уникальном имени среди импортированных документов. Дополнительно:

- разрешить цепочки extends с лимитом и обнаружением циклов;
- разрешить extends только внутри import-closure документа;
- явно описать, что наследуются только `fields`.

---

### P0-5. Срез не гарантирует целостность модели

**Где:** ТЗ §5, System Design §1.2, §3.2.

**Проблема:** срез — это пересечение фильтров `sources` и `generators[].input`. Если генератор выбирает `entities: [User]`, а `User` ссылается на `PostStatus`, то enum может не попасть в срез. Что получит плагин — сломанную модель или enum будет добавлен автоматически? Не описано. Также не описано поведение при неизвестных именах в фильтрах: ошибка или тихий пустой результат?

**Предложение:**

1. Определить **closure-семантику**: после выбора entities автоматически включать все транзитивно referenced enums/types. Либо явно запрещать срезы с «висячими» ссылками и выдавать Error.
2. Неизвестное имя в `input.entities/enums/types` — **Error** с указанием источника.
3. Описать порядок: composition → глобальная валидация → slice → валидация среза → генерация.
4. Добавить в ТЗ пример среза с зависимым enum.

---

### P0-6. Форматы нерасширяемы, а генератор не знает формат

**Где:** ТЗ §3.2, §3.4, §6.3; System Design §2.5, §3.1.

**Проблемы:**

- Формат-плагин «может добавлять типы», но в `FormatPlugin` нет API для регистрации примитивов. `PRIMITIVE_TYPES` — закрытый `Literal`.
- Формат-плагин «может добавлять поля» (`column.generated`), но `Field` не имеет `metadata`/`extra`, а `extra="forbid"` отклонит такие поля. `metadata` есть только у `Entity` и `SourceModel`.
- `GeneratorInput` не содержит ни `format`, ни `version` документа. SQL-генератор не узнает, что модель распарсена как `sql-model`.
- Не описано, можно ли смешивать `entity-model` и `sql-model` в одном запуске. Если да, куда деваются format-specific поля?
- Нет базового класса/хуков, помогающих формат-плагину «расширять, а не заменять» базовый формат.

**Предложение:**

1. Добавить `metadata: dict[str, Any]` (namespaced by plugin id) во все модели: `Field`, `Enum`, `CustomType`, `Entity`, `SourceModel`.
2. Добавить в `FormatPlugin`:
   - `primitive_types: set[str]`;
   - `config_schema`/`parse_extension` hooks;
   - базовый класс `EntityModelFormat` с переопределяемыми хуками.
3. Передавать в `GeneratorInput`/`GenerationContext`: `format`, `format_version`, `run_id`, `config_dir`.
4. Зафиксировать правило: все `sources` одного запуска должны иметь один формат, либо формат-плагин явно объявляет совместимость. Для v1 рекомендую требовать один формат.

---

### P0-7. Манифест, `on_conflict: skip` и cleanup небезопасны

**Где:** ТЗ §10; System Design §8.2–8.4.

**Проблемы:**

- Манифест пишется в `output_dir/.mg-manifest.json` и содержит одно поле `generator`. Если два генератора пишут в один `output_dir`, манифесты перезаписывают друг друга.
- При `on_conflict: skip` существующий файл не перезаписывается, но остаётся ли он «управляемым»? Если нет — cleanup удалит его как orphan. Если да — cleanup может удалить файл, изменённый вручную.
- Cleanup «только по манифесту» всё равно опасен: устаревший манифест от удалённого генератора, смена `output_dir`, удаление `.git`/пользовательских файлов.
- `generated_at` в манифесте делает его недетерминированным; если манифест коммитится, diff шумит.
- Не описаны блокировки при параллельных запусках.
- `--clean` есть в §10, но отсутствует в таблице флагов §8.2; `mg clean` отсутствует в списке команд §8.1.

**Предложение:**

1. Один манифест **на генератор**: `.mg/manifests/<generator-id>.json` (или общий файл с map по генераторам).
2. Добавить `manifest_version`, `plugin_version`, `format`, `sha256` каждого артефакта, `source_hash`, `config_hash`.
3. Ввести **ownership check**: перезаписывать файл можно, только если он есть в манифесте этого генератора или содержит generated-marker. Иначе — Error и `--force`.
4. `skip` должен записывать файл как принадлежащий генератору, но не менять содержимое.
5. Cleanup удаляет только файлы, принадлежащие манифесту этого генератора; никогда не трогает `.git`, `.mg`, скрытые и пользовательские файлы. По умолчанию — `off` в non-tty; `--yes` обязателен.
6. Добавить lock-файл `.mg/lock` или явно объявить single-writer.
7. Добавить `--dry-run`-план: create/update/skip/delete.
8. Внести `--clean`, `mg clean`, `--force`, `--yes`, `--check` в CLI-спеку.

---

### P0-8. Публичный API библиотеки не совпадает с README

**Где:** README, ТЗ §6.2, System Design §2.

**Проблемы:**

- README: `engine = Engine(AppConfig(), rules); results = engine.generate()`.
- System Design §2: `Engine` и `EngineReport` не определены и не входят в публичный API.
- ТЗ §6.2 экспортирует `GeneratorPlugin, GeneratorInput, GenerationResult, Artifact, GenerationContext, SourceModel, Entity, Field, Enum, CustomType`.
- System Design §2 добавляет `ImportedFile, NamingStyle`.
- README использует `transform`, которого нет в списке ТЗ.
- `GeneratorConfig`, `Diagnostic`, исключения — нужны плагинам/библиотеке, но не экспортированы.
- Библиотечный сценарий не должен вызывать `setup_logging()` с `force=True`, иначе он ломает logging приложения-хоста.

**Предложение:**

1. Определить библиотечный фасад:

```python
class Engine:
    def __init__(self, config: AppConfig, rules: GeneratorRules,
                 generators: PluginRegistry | None = None,
                 formats: FormatRegistry | None = None): ...
    def build(self) -> EngineReport: ...      # без записи
    def generate(self) -> EngineReport: ...   # с записью
```

2. Экспортировать: контракты, `NamingStyle`, `transform`, `GeneratorConfig`, `Engine`, `EngineReport`, `Diagnostic`, базовые исключения.
3. Добавить `py.typed`, `__all__`, политику стабильности/депрекации.
4. Сделать логирование opt-in: `NullHandler`, не трогать root logger, не использовать `force=True` в библиотеке.
5. Синхронизировать README, ТЗ §6.2 и System Design §2.

---

### P0-9. YAML: заявлена 1.2, используется PyYAML 1.1

**Где:** ТЗ §14, §3.1; System Design §4.1, §12.

**Проблемы:**

- PyYAML реализует YAML 1.1, а не 1.2. Следствия: `on/off/yes/no` парсятся как boolean, `1.0` — как float, даты — как `date`, возможны sexagesimal-значения.
- `version: 1.0` без кавычек станет float, а Pydantic v2 не приводит float к `str` — пользователь получит неочевидную ошибку.
- `default: 2026-11-10` станет `date`, который не входит в `str | int | float | bool | None`.
- Дубликаты ключей YAML `safe_load` молча перезаписывает.
- Мульти-документный YAML (`---`) не описан.
- Anchors/aliases могут использоваться для DoS.

**Предложение:**

1. Либо перейти на `ruamel.yaml` (YAML 1.2), либо явно объявить поддержку YAML 1.1 и запретить неоднозначные скаляры.
2. Включить загрузчик с обнаружением дубликатов ключей.
3. Нормализовать `version` (принимать `1.0` и `"1.0"`) или требовать строку с понятной ошибкой.
4. Разрешить `date`/`datetime` в `default` либо требовать ISO-строку и явно это документировать.
5. Описать поведение при нескольких документах в файле.
6. Добавить лимиты на размер/aliases, если модели могут приходить из недоверенных PR.

---

### P0-10. Внутренняя модель `Field` конфликтует с `pydantic.Field`

**Где:** System Design §3.1.

**Проблема:** в одном модуле определяется `class Field(BaseModel)` и тут же используется `Field(...)` из Pydantic. В теле класса это сработает, но после определения глобальное имя `Field` будет указывать на модель. Любое последующее `Field(...)` в других моделях сломается или создаст вложенную модель. Аналогично `Enum` конфликтует со stdlib.

**Предложение:** переименовать внутренние модели в `FieldDef`, `EnumDef`, `CustomTypeDef` (или импортировать Pydantic как `pyd`). Публичные имена можно сохранить через алиасы, но внутри — без коллизий.

---

### P0-11. «Замороженные» модели и кэшированные индексы не согласованы

**Где:** System Design §2.1, §3.1.

**Проблемы:**

- `GeneratorInput` назван «замороженным», но `frozen=True` не задан; вложенные `SourceModel` и `dict` изменяемы.
- `GenerationContext.variables` — общий mutable dict для всех плагинов; один плагин может испортить контекст другому.
- `SourceModel` с `validate_assignment=True` и `PrivateAttr`-картами: при замене `entities` или мутации списка карты не пересобираются, валидация не срабатывает.
- Карта `types` вообще отсутствует.
- Построение карт до проверки дубликатов молча схлопывает одинаковые имена.

**Предложение:**

- Сделать контрактные модели `frozen=True`, коллекции — tuple.
- `GenerationContext` копировать на каждого генератора (или делать immutable).
- Карты строить лениво с инвалидацией либо после валидации дубликатов; добавить `type_map`.
- Не обещать «замороженность» без `frozen=True`.

---

### P0-12. Не определены базовые пути и приоритет `-o`

**Где:** ТЗ §3.5.3, §5, §8; System Design §5.2, §7.1.

**Проблемы:**

- Относительно чего разрешаются `sources[].path`, `output_dir`, `templates`, `cache_dir` — cwd или каталог `.mg.yaml`? Для импортов правило есть, для остального нет.
- `mg config` ищет `.mg.yaml` вверх по дереву; тогда относительные пути логичнее считать от файла конфига, а не от cwd.
- Не описан приоритет `--output/-o` и `generators[].output_dir`.
- Не описано, можно ли задавать абсолютные пути для sources/output и запрещены ли они для imports (сейчас запрещены только imports).

**Предложение:**

- Зафиксировать: все пути в `.mg.yaml` разрешаются относительно каталога конфига; CLI-пути — относительно cwd.
- `-o` задаёт корень, итоговый путь = `-o / generator.output_dir / artifact.path`; либо `-o` полностью переопределяет `output_dir` — выбрать одно и записать.
- Явно описать `expanduser`, отсутствие env-подстановок, поведение абсолютных путей.
- Ограничить импорты project root (или добавить `--allow-outside-imports`) — иначе модель может прочитать произвольный файл через `../`.

---

### P0-13. ADR ссылается на несуществующий `enum extends`

**Где:** ADR-0001 §3, решение #4.

**Проблема:** «Enum с тем же name — ошибка, кроме случая, когда один определён через extends другого». Но в схеме у `Enum` нет `extends`. Это противоречие: либо функция не описана, либо ADR ссылается на несуществующее.

**Предложение:** убрать оговорку из ADR либо добавить `Enum.extends` в ТЗ и правила merge. Для v1 проще убрать.

---

## 3. Предложения по ТЗ v1.1

### §1. Цель и назначение

- Добавить раздел **«Не-цели»**: нет reverse engineering БД, нет выполнения миграций, нет relations/FK в ядре, нет встроенных генераторов, нет binary-артефактов (если это решение), нет incremental-генерации в v1.
- Явно сказать, что проект — **CLI и библиотека**, а не только CLI.
- Добавить сравнение с аналогами (datamodel-code-generator, OpenAPI Generator, Prisma, sqlacodegen): чем проект отличается и для чего его выбирать.

### §2. Термины

- Добавить: source, slice, composition, document, manifest, orphan, format plugin, generator input.
- Развести «документ модели» и «модель» (сейчас оба называются model).

### §3. Формат модели

- Добавить `metadata` во все сущности или убрать его из System Design.
- Добавить `constraints` в описание `Field` (сейчас есть только у `types`).
- Синхронизировать имена constraints: `min/max` в ТЗ vs `min_value/max_value` в System Design.
- Описать, что `CustomType.base` может ссылаться только на примитив или другой custom type; цепочки — с обнаружением циклов и лимитом.
- Определить слияние constraints типа и поля: поле переопределяет по атрибуту, остальное наследуется (или запретить смешение).
- Добавить валидации: `min <= max`, `min_length <= max_length`, применимость constraint к базовому типу, default внутри constraints/enum values.
- Для enum: уникальность имён и значений, непустой список, допустимые типы значений (string/integer, без float, если так решено).
- Для `updated_at`: выбрать `date` или `datetime`, зафиксировать UTC и поведение YAML-скаляра.
- Добавить pattern для `Entity.name`, `Enum.name`, `CustomType.name`, `EnumValue.name`, `imports.as`.
- Убрать проверку «SQL-инъекции в default» из ядра — это зона SQL-формата, иначе ложные срабатывания.
- Ограничить warning про `updated_at < mtime` file-per-entity сценарием или сделать opt-in: в monolith и CI он будет шуметь.

### §4. Принцип «данные отделимы от генерации»

- Добавить пример: одна модель → SQL + TS + OpenAPI, и что именно делает каждый плагин.
- Уточнить, что генераторы не пишут файлы сами, а только возвращают артефакты.

### §5. Метаконфиг

- Привести `sources` к одной схеме (см. P0-3).
- Описать closure-семантику среза (P0-5).
- Описать приоритет `-o` и `output_dir` (P0-12).
- Убрать или реализовать `required_by_default`.
- Для `variables` зафиксировать: все значения приводятся к строкам; секреты не логируются и редактируются в `mg config show`.
- Для `options` добавить JSON Schema от плагина и поведение при неизвестных ключах.
- Описать `enabled: false`: загружается ли плагин, применяется ли cleanup, переопределяет ли `-g`.
- Описать пересечение `output_dir` у нескольких генераторов и конфликты путей.

### §6. Контракты плагинов

- Синхронизировать публичный список API (P0-8).
- `id` — либо атрибут, либо property; сейчас в примерах и то, и другое.
- `validate_config` должен возвращать структурированные `Diagnostic`, а не `list[str]`; описать, когда вызывается и что происходит при ошибках.
- Описать поведение при исключении из плагина: ловится, логируется, остальные генераторы продолжаются, exit 1.
- Описать, что делать, если `GenerationResult.errors` непустой, но artifacts тоже есть: артефакты отбрасываются.
- Добавить `api_version` для `FormatPlugin` и политику совместимости.
- Описать, как формат-плагин добавляет примитивы, поля и валидацию (P0-6).
- Определить `Artifact.path`: только относительный POSIX, без `.`, `..`, абсолютных путей, NUL, Windows-drive, зарезервированных имён; запретить `.mg*`.
- Обнаруживать дубликаты путей внутри одного результата и между генераторами.
- Зафиксировать: text-only UTF-8, LF, без BOM. Binary — явная не-цель или отдельный тип артефакта.

### §7. Шаблонизация

- Добавить рекомендацию плагинам использовать `importlib.resources` для шаблонов в wheel.
- Описать, как пользователь переопределяет шаблоны (`options.templates_dir`) и как это валидируется.
- Уточнить, что core не предоставляет Jinja2.

### §8. CLI

- Переименовать `--format` в `--output-format`/`--report`, чтобы не путать с форматом документа.
- Добавить `mg clean`, `mg gen info`, `mg format list`, `mg model schema`, `mg config schema` (P2), `mg doctor` (P2).
- Добавить `--check` (проверка drift без записи), `--plan`, `--force`, `--yes`.
- `-g` должен поддерживать и запятую, и повторение; описать парсинг.
- `--var`: запретить пустой ключ, описать дубликаты (last wins), экранирование `=`, приведение к строке.
- `mg watch`: те же флаги, что у generate; игнорировать `output_dir`, `.git`, `.mg`; перезагружать `.mg.yaml`; описать initial build и Ctrl+C.
- `mg init`: описать, что создаётся, интерактивность, `--force`, не перезаписывать существующее.
- `mg config show`: показывать resolved paths и redact секретов; `--format json`.
- `mg model validate`: несколько файлов/каталогов; JSON-диагностика.
- Определить exit codes для ошибок парсинга модели vs ошибок конфига (сейчас неясно: 1 или 2).

### §9. Валидация

- Завести **единый каталог кодов** диагностик в ТЗ (MG1xx parse, MG2xx model, MG3xx composition, MG4xx plugin, MG5xx write).
- Синхронизировать проверки ТЗ и коды System Design: сейчас часть проверок без кодов.
- Добавить проверки: неизвестные имена в фильтрах, пустой enum, дубликаты enum values, циклы custom types, default вне constraints, default не из enum, конфликты case-insensitive имён (warning).
- Описать приоритет: ошибки валидации останавливают весь запуск или только затронутые генераторы.
- `--strict` должен иметь ignore-список по кодам, иначе шумные warning'и делают его непригодным в CI.

### §10. Запись артефактов

- Переписать раздел по P0-7: ownership, per-generator manifest, cleanup safety, locks, стиaging.
- Уточнить атомарность: per-file или batch? Что происходит при падении на середине? Откат? `fsync`?
- Указать, что staging должен быть на той же ФС, иначе `os.replace` не атомарен.
- Описать поведение `--dry-run` (не создаёт каталоги, показывает конфликты).
- Описать обработку symlink'ов, case-insensitive FS, Unicode NFC/NFD, длины путей.
- Зарезервировать `.mg/`, `.mg-manifest.json`, `.mg-staging-*`, `.mg-lock`.

### §11. Архитектура

- Разделить `ModelDocument`/`SourceModel`/`ModelSlice` (P0-2).
- Добавить модуль `planning` (что будет записано) и `locking`.
- Убрать/реализовать `cache_dir`: сейчас он есть в AppConfig, но не используется.
- Уточнить, что `format` и `version` документа должны попадать в контекст генератора.
- Обновить опечатку «v1.0» в примечании про entry points на v1.1/core.
- Убрать `required_by_default` или описать.

### §12. Качество

- Переписать критерии производительности: сейчас «<50 мс на файл до 1000 сущностей» не имеет методики и reference-машины. Предложить benchmark с фиксированной моделью, 3 прогона, медиана, допуск в CI.
- Добавить security-тесты: path traversal, symlink, cleanup, YAML duplicate keys, alias DoS, чтение вне project root.
- Добавить тесты детерминизма: повторный запуск → идентичные байты; сортировка артефактов; отсутствие абсолютных путей.
- Добавить contract-тесты plugin API (отдельный testkit).
- Добавить CI-матрицу: Linux/macOS/Windows, Python 3.11/3.12.
- Добавить `py.typed`, `types-PyYAML`, конфиги ruff/mypy/pytest.

### §13. Roadmap

- Добавить definition of done и acceptance criteria для каждого этапа.
- В v0.1 включить reference-плагин (не встроенный генератор, а пример/фикстуру), иначе нечего end-to-end тестировать.
- Явно указать, как в v0.1 ведут себя поля конфига, которые появятся в v0.2 (`cleanup`, `on_conflict: skip|error`): warning + игнор или ошибка.
- Добавить этап «docs/schema/reference plugin/CI» до v0.1.

### §14. Открытые вопросы

- Для каждого вопроса добавить owner, дату решения и критерий закрытия.
- Добавить вопросы: mixed formats, binary artifacts, library API stability, YAML dialect, cleanup ownership.

### §15. Пример end-to-end

- Добавить пример с импортом и extends после того, как будет зафиксирован их синтаксис.
- Добавить пример с генератором, который генерирует cross-entity артефакт (barrel/migration).
- Показать ожидаемый `--format json` отчёт.

---

## 4. Предложения по System Design

### §1. Обзор и поток данных

- Добавить шаг `validate_config` и шаг проверки версии формата.
- Явно показать, где строится `ModelSlice` и где проверяется closure.
- Добавить в диаграмму `Planning` и `Lock`.

### §2. Интерфейсы плагинов

- `GeneratorInput`: `model: ModelSlice`, `format`, `format_version`, `run_id`.
- `GenerationContext`: `variables` (не `vars`), `naming_hint`, `imports`, `sources` с относительными путями, `config_dir`.
- `ImportedFile`: всегда `bytes`; добавить helper `text(encoding="utf-8")`; описать, что путь в артефактах должен быть относительным.
- `Artifact`: добавить `encoding`, `mode`? Для v1 достаточно text-only, но зафиксировать.
- `GenerationResult`: `warnings/errors: list[Diagnostic]`, а не `list[str]`.
- `GeneratorPlugin`: выбрать один способ объявления `id`; `api_version: ClassVar[Literal["1"]]`.
- `validate_config` → `list[Diagnostic]`; описать lifecycle и обработку ошибок.
- `FormatPlugin`: `parse(raw, base_path) -> ModelDocument`; `supported_versions`; `primitive_types`; base class с хуками.

### §3. Внутренние модели

- Переименовать `Field`/`Enum` (P0-10).
- Ввести `UNSET` для default (P0-1).
- `SourceModel`/`ModelSlice` (P0-2).
- Добавить `metadata` во все модели.
- Исправить `CustomType.base: PRIMITIVE_TYPES | str` → `str` + validator.
- Исправить кэш-карты: immutable/tuple, `type_map`, построение после проверки дубликатов.
- `InputSlice`: `None` vs `[]` — определить; неизвестные имена — Error.
- `SourceConfig`: привести к ТЗ (P0-3).
- `GeneratorRules.version`: валидировать и поддерживать только известные версии.
- `DefaultsConfig.naming_convention`: решить, `None` или `SNAKE` по умолчанию; если это hint, лучше `None`.

### §4. Парсинг и композиция

- `parse_document` → `ModelDocument`; убрать `data.get("format", ...)`, `format` обязателен.
- Проверять `version` через реестр; неизвестная версия — понятная ошибка.
- Добавить duplicate-key loader.
- `_resolve_document`: увеличивать depth, использовать `try/finally`, кэшировать уже разобранные пути, хранить `doc_root` явно.
- `_merge_or_register`: описать реальный алгоритм merge, а не заглушку.
- `merge_entity`: дописать полностью, включая цепочки extends, циклы, дубликаты полей и порядок.
- `Validator`: добавить source path в диагностику; коды для всех проверок;`--strict`-политику; разделить Pydantic-ошибки и semantic warnings.
- Убрать `Error?` из таблицы null-matrix.

### §5. Configuration Layer

- Синхронизировать источники AppConfig с ТЗ: либо реализовать config file, либо убрать его из списка приоритетов.
- `config_file` переименовать в `rules_file`, чтобы не путать с app config.
- Убрать неиспользуемый `cache_dir` или описать кэш.
- `discover()`: условие остановки, несколько конфигов, приоритет, путь к конфигу в отчёте.
- Логирование: `NullHandler`, opt-in, без `force=True` в библиотеке; redaction секретов; JSON-логи для CI (P2).

### §6. Plugin Loader

- Ленивая загрузка: `-g oracle-ddl` не должен падать из-за сломанного стороннего плагина.
- Дубликаты `id` — Error с перечнем distribution'ов, а не silent overwrite.
- `plugin.id != ep.name` — Error (ТЗ говорит «должен совпадать»), а не warning.
- Добавить метаданные плагина: distribution, version, api_version.
- Не загружать все entry points для `mg gen list`; либо robust-режим с ошибками в списке.
- `api_version` mismatch: сообщение должно содержать имя distribution и требуемую версию ядра; завести mapping api_version → min core version.
- Сортировать плагины по id для детерминизма.

### §7. CLI

- `--format` → `--output-format` (P0).
- `Optional[list[Path]]` для positional arguments.
- Добавить `--check`, `--plan`, `--force`, `--yes`.
- `parse_vars`: пустой ключ, дубликаты, `=` в значении.
- `EngineReport` и JSON-схема отчёта: `success`, `diagnostics`, `generators[]`, `artifacts[]`, `timings`, `exit_code`.
- TextFormatter: показывать create/update/skip/delete, а не только `[✓]`.
- Ctrl+C → 130; поведение watch при ошибках генерации.
- Исправить опечатки (`илиphans`).

### §8. Artifact Writer

- Полностью переписать по P0-7.
- `validate_artifact_path`: `PurePosixPath`, запрет absolute/`..`/NUL/drive/reserved, проверка после join, case-collision, Unicode.
- Ownership check и `--force`.
- Per-file atomic + понятный контракт batch (что откатывается, что нет).
- Staging внутри `output_dir` (та же ФС), уникальные имена, очистка при старте/сигнале.
- Manifest: schema, hashes, plugin/core/format versions, atomic write, deterministic mode.
- Cleanup: только owned files, preview, non-tty safety, запрет `.git`/`.mg`.
- Lock.

### §9. Watch

- Игнорировать `output_dir`, `.git`, `.mg`, temp.
- Начальная генерация при старте.
- Перезагрузка `.mg.yaml`; плагины не перезагружаются — задокументировать.
- Debounce и batch изменений.
- Graceful shutdown, exit code.
- Те же флаги, что у generate.

### §10. Структура проекта

- Добавить `core/document.py` (ModelDocument), `core/planning.py`, `engine/locking.py`, `schema/` для JSON Schema.
- Добавить `examples/` с reference-плагином.
- Добавить `LICENSE`, `py.typed`, CI-конфиг.
- `interfaces/generator.py`: `id`/`api_version` контракт.

### §11. Тестирование

- Golden-тесты должны использовать **тестовый reference-плагин**, иначе core нечего генерировать.
- Property-тест переписать: любой dict → только `DocumentError`/`ValidationError`, без `KeyError`/`AttributeError`/`TypeError`; invalid не должен «тихо» приниматься.
- Round-trip: учесть заполнение `EnumValue.value`, `UNSET`, `date`/`datetime`; иначе тест будет ложноположительным.
- Добавить тесты: path traversal, symlink, cleanup, duplicate keys, case collisions, concurrent runs, encoding, Windows.
- Добавить contract-тесты plugin API и тесты совместимости версий.
- Добавить benchmark и CI-матрицу.

### §12. Зависимости

- `watchdog` — optional extra `[watch]`, раз он lazy.
- `types-PyYAML` в dev.
- `py.typed`, `license`, `classifiers`, `[project.urls]`.
- Рассмотреть Python 3.11 вместо 3.12 для охвата (если нет 3.12-специфики).
- Добавить конфиги ruff/mypy/pytest/coverage.
- Проверить доступность имени `metadata-generator` и CLI `mg` на PyPI/в системах (есть сторонний редактор `mg`); при конфликте — `mdgen`/`metagen`.

### §13. Сводка решений

- Добавить решения: null-семантика, ownership/manifest, library API, YAML dialect, mixed formats.
- Исправить грамматику/опечатки: «App-related плагину не передаётся», «editatable», «архивные плагины».

---

## 5. Сквозные улучшения

1. **Трассируемость требований.** Дать каждому требованию ID (`FR-001`, `NFR-001`) и матрицу «требование → тест → ADR». Сейчас ссылки только по разделам, это затруднит приёмку.
2. **RFC 2119.** Использовать must/should/may и явные приоритеты MVP/Future.
3. **Каталог ошибок.** Единый список кодов, сообщений, severity и exit code. Сейчас коды есть только в System Design и неполные.
4. **Матрица версий.** Развести: версия инструмента, версия схемы документа, версия `.mg.yaml`, версия manifest, версия plugin API, версия отчёта JSON. Сейчас «1.0/1.1/0.1.0» смешаны.
5. **Политика совместимости.** Python, ОС, document schema, plugin API, manifest; правила deprecation.
6. **Security-раздел.** Path traversal, symlink, cleanup, импорт вне project root, secrets в vars/логах, ReDoS в `pattern`, недоверенные плагины.
7. **Детерминизм.** Сортировка sources/artifacts/plugins, относительные пути, LF/UTF-8, `SOURCE_DATE_EPOCH`, golden-нормализация, отсутствие timestamp в коммитируемых артефактах.
8. **Library-first.** `Engine.build()` без записи, инъекция реестров плагинов, отсутствие глобальных side effects, типизированный публичный API.
9. **Reference-плагин.** Без встроенных генераторов проект не даёт ценности «из коробки». Нужен пример (`examples/json-schema-generator` или `echo`), который одновременно служит документацией, golden-фикстурой и contract-тестом.
10. **Документация.** Добавить `docs/adr/index.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, plugin guide, model reference, config reference, error catalog.
11. **Актуализация.** `.session-context.md` содержит устаревшие решения (aliases, «убран validator.py», `extends` в header) и не должен быть каноническим источником. Либо обновить, либо убрать из репозитория и перенести решения в ADR.
12. **Мелкие несоответствия.** Дата v1.0 в `docs/requirements/index.md` — `2025-11-03`, а в `.session-context.md` первая сессия — `2026-11-03`; проверить. В System Design §12 примечание говорит «v1.0» вместо v1.1. В ТЗ §3.5.1 остался зачёркнутый фрагмент.

---

## 6. Приоритетный план

### До v0.1 (P0)

1. Зафиксировать null-семантику и sentinel `default`.
2. Ввести `ModelDocument` / `SourceModel` / `ModelSlice`.
3. Синхронизировать схему `sources`.
4. Определить `entity.extends` и closure среза.
5. Определить расширяемость форматов и передачу `format/version` генератору.
6. Переписать artifact ownership/manifest/cleanup.
7. Определить публичный API библиотеки.
8. Решить вопрос YAML 1.1/1.2 и duplicate keys.
9. Убрать конфликт `Field`/`Enum`.
10. Зафиксировать базовые пути и приоритет `-o`.

### До v0.2 (P1)

11. Структурированные `Diagnostic` и каталог кодов.
12. Единая политика ошибок плагинов и `validate_config`.
13. `--check`, `--plan`, `--force`, `--yes`, `mg clean`.
14. Watch: ignores, reload, флаги.
15. Security-тесты и path-hardening.
16. CI-матрица, reference-плагин, contract-тесты.

### Позже (P2)

17. JSON Schema для модели/конфига, `mg model schema`, IDE-интеграция.
18. Инкрементальная генерация и кэш.
19. Provenance на уровне entity.
20. Публикация docs-site и plugin ecosystem.

---

## 7. Что менять не нужно

- Изоляция сущностей и отсутствие relations в ядре — сильное, нейтральное решение.
- Два типа плагинов (generator/format) и entry points — правильная масштабируемая модель.
- Цельный срез модели на входе генератора — верно для cross-entity артефактов.
- `naming_convention` как подсказка, а не молчаливое переименование — правильно.
- Atomic write + manifest как идея — правильное направление, нужна лишь безопасная реализация.
- ADR-практика и фиксация merge-семантики — очень полезно; стоит продолжить для null-семантики, ownership и plugin API.
