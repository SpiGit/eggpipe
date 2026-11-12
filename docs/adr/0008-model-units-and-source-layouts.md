# ADR-0008: Model unit, раскладки источников и layer merge

- **Статус:** принято
- **Дата:** 2026-11-12
- **Связанные документы:** [ТЗ v1.4 §3.5, §5](../requirements/v1.4.md), [ADR-0001](./0001-composition-merge-semantics.md), [ADR-0007](./0007-format-inheritance.md)

---

## 1. Контекст

До v1.3 источники могли быть файлом или каталогом, а каждый YAML был самостоятельным
документом. Расширение формата через копию всего набора файлов приводило к дублированию:
те же данные лежали в `model/` и `model-postgres/`, отличаясь только заголовком `format`.

Нужно:

- один входной YAML на сущность;
- возможность разнести слои формата по файлам;
- явные раскладки `monolith`, `file-per-model`, `directory-per-model`;
- ресурсы, не участвующие в модели;
- предсказуемый аддитивный merge.

## 2. Решение

### 2.1. Model unit

- Модель = одна логическая сущность (`Entity`).
- В `monolith` один файл может содержать несколько моделей.
- В `file-per-model` один YAML содержит одну модель.
- В `directory-per-model` каталог содержит одну модель и несколько YAML-слоёв.

### 2.2. Раскладки

| Layout | Обязательные поля | Смысл |
|--------|-------------------|-------|
| `monolith` | `path` (файл) | Один файл, несколько сущностей |
| `file-per-model` | `path` (каталог), `files` | Один YAML на сущность |
| `directory-per-model` | `path`, `model_dirs`, `files` | Каталог на сущность, слои и ресурсы |

- `layout` опционален для обратной совместимости: файл → `monolith`, каталог → `file-per-model`.
- Для `directory-per-model` `model_dirs` и `files` обязательны; скрытых значений по умолчанию нет.
- `model_dirs`/`files` — glob или точный список.
- `models.<dir>` переопределяет `files`/`resources` для конкретного каталога.
- `resources` задаются явно и не парсятся как модель.

### 2.3. Слои формата

- Один файл — один формат.
- Несколько файлов одного формата в модели не поддерживаются (MG029).
- Форматы слоёв должны образовывать одну цепочку `extends`; иначе MG029.
- Порядок слоёв вычисляется по `extends`; состав файлов задаётся явно.
- Базовый файл модели — полный: валидируется `full_model` своего формата.
- Файлы-дельты после базового валидируются `layer_model` своих форматов.
- После merge итог — `full_model` самого производного формата.
- В `monolith`/`file-per-model` файл полный, layer merge нет.
- Слой-дельта содержит ровно одну сущность (MG031).
- Пустой каталог модели — Warning (MG027) и пропуск.
- В v1.4 файлы-слои не используют `imports`/`extends`; кросс-сущностная композиция
  остаётся для `monolith`/`file-per-model`. Совмещение — future.

### 2.4. Layer merge

- Merge аддитивный: новые entity/enum/type/field/metadata-ключи.
- Расширение может добавлять поля к существующей сущности.
- Одинаковое имя с разными значениями — Error (MG029).
- Переопределение существующих значений не поддерживается.
- Scalar (`description`, `version`, `updated_at`) можно задать только если он ещё не задан;
  одинаковое значение допустимо.
- `metadata` мержится рекурсивно; конфликт скаляров — Error (MG029).
- Поля: сначала базовые в исходном порядке, затем новые в порядке слоёв.
- Enum: новые значения добавляются; удаление/переименование запрещено.
- CustomType: новые типы добавляются; изменение базового типа запрещено.
- Named lists merge by `name`: `entities`, `fields`, `enums`, `enum.values`, `types`.
  Base order is preserved; new items append in layer order.
- Existing items are merged recursively; duplicate key within one layer is MG029.
- Rename/delete/reorder in layer merge are not supported.
- Other lists declare `MergePolicy`: `KEYED` (default for named core lists), `APPEND`, `UNION`,
  `ERROR`. Unknown list without policy is `ERROR` (MG029).
- `metadata` lists use `APPEND`; dicts merge recursively; scalar conflicts are MG029.
- Provenance: `Entity.source` — базовый слой, `Entity.layer_sources` — все слои,
  `FieldDef.source` — слой, где поле определено.

### 2.5. Composition merge

`imports` и `entity.extends` остаются механизмами кросс-сущностной композиции.
[ADR-0001](./0001-composition-merge-semantics.md) уточняется:

- при `extends` наследуются `description`, `version`, `updated_at`, `metadata`, `fields`;
- child может переопределять scalar-атрибуты;
- `metadata` мержится аддитивно;
- поля с тем же именем замещают родительские (как и раньше).

Layer merge (§2.4) строже composition merge: в слоях переопределения запрещены.

### 2.6. Ресурсы

- Ресурсы задаются явно в `.mg.yaml`.
- Alias — относительный путь без расширения; можно переопределить через `as`.
- Коллизия alias — Error (MG032).
- Ресурсы доступны через `GenerationContext.imports`, проверяются на path traversal/symlink
  и попадают в watch.

## 3. Последствия

- Один набор данных на сущность, без копий под каждый формат.
- Слои формата можно добавлять без изменения базовых файлов.
- Появляются новые диагностики MG027/MG029/MG031/MG032.
- Нужны новые поля `Entity.format`, `format_version`, `layer_sources`; `FieldDef.source`.
- `directory-per-model` требует явной конфигурации; старые конфиги продолжают работать
  через `layout` по умолчанию.

## 4. Альтернативы

- Копировать модель под каждый формат — отклонено: дублирование и рассинхронизация.
- Автоматически обходить все YAML в каталоге без конфигурации — отклонено: неоднозначно
  с ресурсами и слоями.
- Разрешить переопределения в layer merge — отклонено: скрытые ошибки и неоднозначный diff.
- Смешивать `imports`/`extends` со слоями в v1.4 — отложено: слишком сложный порядок merge.
