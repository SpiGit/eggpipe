# Eggpipe

- **Статус:** имя выбрано
- **Дата:** 2026-11-12
- **ТЗ:** [v2.1](requirements/v2.1.md)
- **Бренд:** EggPipe
- **Пакет / import / CLI:** `eggpipe`
- **Конфиг:** `.eggpipe.yaml`
- **State:** `.eggpipe/`
- **PyPI:** свободно
- **npm:** свободно
- **GitHub:** 0 совпадений по имени
- **Домены:** `.com` и `.dev` свободны на 2026-11-12

---

## 1. Что делает инструмент

`Eggpipe` читает YAML-описание модели данных и превращает его в артефакты:

- SQL DDL и миграции;
- Pydantic/ORM/dataclass-модели;
- TypeScript-типы;
- OpenAPI-схемы;
- любые другие выходы через плагины.

Одна модель — много артефактов. Генераторы подключаются как плагины.

---

## 2. Почему Eggpipe

Название соединяет две идеи:

- **egg** — яйцо, начало, то, из чего что-то рождается;
- **pipe** — труба, pipeline, поток данных, Unix pipe.

Модель — это яйцо. Генераторы — труба/pipeline. Артефакты — то, что вылупляется.

Это даёт:

- короткое, запоминающееся имя;
- шутливость без потери технического смысла;
- готовую метафору для логотипа и документации;
- связь с pipeline/потоком данных;
- отличие от перегруженных `model`, `metadata`, `entity` и `schema`.

---

## 3. Как выбирали

Основные критерии:

- не использовать перегруженное `model`;
- не использовать `metadata`;
- имя должно быть коротким и произносимым;
- свободно на PyPI, npm и желательно в домене;
- нет прямого конкурента;
- чистая фонетика для русскоязычной аудитории;
- есть визуальная метафора для логотипа;
- можно объяснить за одну фразу.

Рассматривали направления:

- `model*`: `modelmill`, `modelseed`, `modelmarmot`, `modelotter`;
- `entity*`: `entityforge`, `entitygen`, `entigenome`;
- `prism*`: `prismix`, `prismal`, `prismora`, `prismforge`, `prismloom`;
- `blueprint*`: `blueprintry`, `blueprintix`, `Blueprint Projector`;
- `genome*`: `genomloom`, `genommill`, `genomtype`;
- `synth*`: `synthosis`, `synthmill`, `synthloom`;
- космос/физика/химия: `bosonforge`, `photonloom`, `cometforge`;
- аббревиатуры: `eggpipe`, `genomflow`, `blueprintpipe`.

Что отклонили:

| Кандидат | Причина |
|----------|---------|
| `metadata-generator` | слишком общее, `mg` конфликтует, слабый бренд |
| `model*` | перегруженное `model` |
| `entitygen` / `entity-gen` | слишком общее, `entity-gen` занят на npm |
| `entigen` | PyPI занят прямым конкурентом «Metamodel entity generator», звучит как антиген |
| `prismix` | PyPI занят AI code synthesis, прямой конкурент |
| `blueprintry` | хороший вариант, но `.com` занят, длинновато |
| `prismloom` | хороший вариант, но длинновато |
| `bosonforge` | чистый, но длинный и менее тёплый |

`eggpipe` выиграл за счёт:

- уникальности: PyPI/npm свободны, GitHub 0;
- свободных `.com` и `.dev`;
- простой и тёплой метафоры;
- технического `pipe` в названии;
- лёгкой истории для лого.

---

## 4. Проверка занятости

На 2026-11-12:

| Канал | Статус |
|-------|--------|
| PyPI `eggpipe` | свободно |
| npm `eggpipe` | свободно |
| GitHub по имени | 0 совпадений |
| `eggpipe.com` | свободен |
| `eggpipe.dev` | свободен |

Проверка не заменяет юридическую проверку товарного знака и поисковую выдачу.

---

## 5. Фонетика и языки

### Русский

- `eggpipe` — «эггпайп»;
- две `g` — это слово `egg`, не ошибка;
- чисто, шутливо, понятно;
- `pipe` читается как «пайп/pipeline».

### Английский

- `eggpipe` — «egg pipe»;
- не обычное слово, легко запоминается;
- есть лёгкая ассоциация с Python egg, но она не мешает.

### Другие языки

- французский: `pipe` имеет сленговое значение, но в tech-контексте читается как pipeline;
- испанский: `huevos` может быть сленгом, но название английское;
- китайский/арабский/турецкий: mild-ассоциации со словом «яйцо»;
- остальные основные языки: нейтрально.

Вывод: для русскоязычной и англоязычной аудитории имя чистое. Во французском consumer-маркетинге
лучше добавить пояснение «egg + pipeline».

---

## 6. Бренд-история

Короткие формулировки:

- «Hatch artifacts from your model.»
- «One model. Many artifacts.»
- «Your model, piped.»
- «Blueprint in. Artifacts out.»
- «Let your model hatch.»

Основная история:

> Модель — это яйцо. Генераторы — pipeline. Артефакты вылупляются.

---

## 7. CLI и конфигурация

Решение:

| Что | Значение |
|-----|----------|
| CLI | `eggpipe` |
| Конфиг | `.eggpipe.yaml` |
| State-каталог | `.eggpipe/` |
| Python package / import | `eggpipe` |
| Entry points | `eggpipe.generators`, `eggpipe.formats` |
| Manifest | `.eggpipe/manifest.json` |
| Lock | `.eggpipe/lock` |

### Почему CLI `eggpipe`

Рассматривали:

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| `eggpipe` | уникально, совпадает с брендом, нет конфликтов | 7 символов |
| `egg` | коротко, шутливо | общее слово, Python egg, возможные конфликты |
| `ep` | очень коротко | слишком общее: episode, endpoint, European Parliament |
| `egp` | аббревиатура | похоже на EGP (египетский фунт, Exterior Gateway Protocol) |
| `pipe` | технично | слишком общее, конфликт с Unix pipe |

`eggpipe` — единственный вариант без смысловой и CLI-путаницы.
`egg`, `ep`, `egp`, `pipe` — не используем как основные команды.

Короткий alias `egg` можно добавить позже, если не будет конфликтов, но не сейчас.

### Почему `.eggpipe.yaml`

Рассматривали:

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| `.eggpipe.yaml` | однозначно, совпадает с CLI, не путается с Python egg | длиннее |
| `.egg.yaml` | коротко, шутливо | слишком общее, путаница с Python egg |
| `.eggp.yaml` | коротко | нечитаемо |
| `.pipe.yaml` | технично | конфликт с Unix pipe/pipeline |
| `eggpipe.toml` | современно | ломает текущий YAML-формат |

Выбран `.eggpipe.yaml`:

- один канонический файл;
- явно принадлежит инструменту;
- не конфликтует с Python egg;
- легко искать;
- `-c` позволяет указать другой файл.

`.yml` как второй вариант не поддерживаем: только `.yaml`.

### Команды

```text
eggpipe generate
eggpipe watch
eggpipe init
eggpipe clean
eggpipe config show
eggpipe config validate
eggpipe config schema
eggpipe model validate
eggpipe model schema
eggpipe gen list
eggpipe gen info <id>
eggpipe format list
eggpipe format info <name>
```

### `generate`

```bash
eggpipe generate [MODELS...]
```

| Флаг | Смысл |
|------|-------|
| `-c, --config PATH` | `.eggpipe.yaml` |
| `-g, --generator ID` | выбранные генераторы |
| `-o, --output PATH` | корень вывода |
| `--var KEY=VALUE` | переменная |
| `--plan`, `--dry-run` | план без записи |
| `--check` | проверка drift без записи |
| `--clean` | cleanup enabled для запуска |
| `--force` | перезапись unowned-файлов |
| `--strict` | warnings → errors |
| `--include-disabled` | включить disabled-генераторы |
| `--allow-outside-imports` | разрешить импорты/ресурсы вне root |
| `--output-format text\|json` | формат отчёта |
| `--ignore MGxxx,...` | игнорировать коды |
| `-q, --quiet`, `-v, --verbose` | вывод |

`--force` не отбирает файлы у другого location.

### `watch`

Те же флаги, что у `generate`, плюс:

```text
--debounce-ms 300
```

### `clean`

```bash
eggpipe clean [--dry-run] [--yes] [--root PATH]
```

- работает по `.eggpipe/manifest.json`;
- не требует `.eggpipe.yaml` и плагинов;
- чистит все locations;
- `--dry-run` показывает план;
- в non-tty нужен `--yes`;
- `--root` указывает каталог проекта, если конфиг не найден.

### `init`

```bash
eggpipe init [PATH] --layout file-per-model|directory-per-model|monolith [--force]
```

- создаёт `.eggpipe.yaml`;
- создаёт пример модели;
- `--layout` обязателен в non-tty;
- в tty можно спросить;
- `--force` перезаписывает существующие файлы.

### `config`

```bash
eggpipe config show
eggpipe config validate
eggpipe config schema
```

- `show` печатает итоговый конфиг с учётом `--var`;
- `validate` проверяет схему и ссылки;
- `schema` печатает JSON Schema для `.eggpipe.yaml`.

### `model`

```bash
eggpipe model validate [MODELS...]
eggpipe model schema --format postgres-model [--version 2.0]
```

- `validate` парсит и валидирует модели;
- `schema --format` печатает JSON Schema выбранного формата;
- `--version` опционален: нет — latest;
- без `--format` печатается JSON Schema `ModelDocument`.

### `gen`

```bash
eggpipe gen list
eggpipe gen info <id>
```

`gen list`:

```text
tpch        TPC-H DDL + Pydantic   input=entity-model   api=1
tpch-ddl    TPC-H PostgreSQL DDL   input=entity-model   api=1
```

`gen info`:

- id, name, api_version;
- `input_formats`;
- source distribution;
- class/decorator;
- доступность.

### `format`

```bash
eggpipe format list
eggpipe format info <name>
```

`format list`:

```text
entity-model    latest=1.0   extends=-
postgres-model  latest=2.0   extends=entity-model   base_versions=1.0→1.0, 2.0→1.0
```

`format info`:

- versions;
- latest;
- extends;
- `base_versions`;
- primitive types;
- имена Pydantic-схем;
- кто из генераторов принимает формат.

### Поиск конфига

- если `-c` не указан, искать `.eggpipe.yaml` в cwd и родительских каталогах;
- остановиться на git root;
- ближайший файл побеждает;
- если не найден — ошибка `2`;
- `clean` использует тот же поиск, но не парсит конфиг.

### Exit codes

| Код | Смысл |
|-----|-------|
| 0 | успех |
| 1 | ошибки модели/генерации/cleanup, drift, strict warnings |
| 2 | config/usage: флаги, конфиг, plugin, format mismatch |
| 130 | Ctrl+C |

### JSON-отчёт

`--output-format json` содержит:

- `report_version: 2`;
- `success`, `exit_code`, `run_id`;
- `diagnostics`;
- `formats`;
- `generators` с `input_formats`;
- плоские `artifacts` с `generator`, `action`, `path`, `sha256`;
- `manifest` locations;
- `stale_locations`;
- `timings`.

### Что переименовывается

До первого релиза без обратной совместимости:

- `mg` → `eggpipe`;
- `.mg.yaml` → `.eggpipe.yaml`;
- `.mg/` → `.eggpipe/`;
- `metadata_generator` → `eggpipe`;
- entry points `metadata_generator.generators` → `eggpipe.generators`;
- entry points `metadata_generator.formats` → `eggpipe.formats`;
- env prefix `MG_` → `EGGPIPE_` (если используется).

CI, docs, примеры и manifest paths обновляются вместе.

## 8. Идеи для логотипа

### 8.1. Яйцо в трубе

- яйцо внутри круглого сечения трубы;
- труба образует кольцо вокруг яйца;
- минималистично, легко масштабируется.

### 8.2. Труба как яйцо

- контур яйца образован изогнутой трубой;
- negative space;
- хорошо работает в одну линию.

### 8.3. Конвейер с яйцами

- яйцо движется по pipe/conveyor;
- на выходе — файлы/артефакты;
- подчёркивает «one model → many artifacts».

### 8.4. Вылупление

- яйцо с трещиной;
- из трещины выходят символы кода, скобки, шестерёнка или файл;
- метафора «артефакты рождаются из модели».

### 8.5. Монограмма EP

- `E` и `P` соединены в форму яйца или трубы;
- подходит для favicon и иконки приложения;
- можно сделать `P` в виде pipe.

### 8.6. Маскот

- цыплёнок/утёнок в трубе;
- яйцо в каске или с очками;
- персонаж, который «вылупляет» артефакты;
- шутливо, но не слишком детско.

### 8.7. Палитра

- eggshell: `#F7F3E8`;
- yolk: `#F2B705`;
- pipeline teal: `#1F7A8C`;
- slate: `#1F2937`;
- accent coral: `#E4572E`.

### 8.8. Стиль

- плоская геометрия;
- толщина линии 1.5–2 px;
- читаемость в 16×16;
- монохромная версия;
- без фотореализма и без Python-логотипа;
- без агрессивных «труб» и тяжёлой индустрии.

### 8.9. Варианты

- icon-only: яйцо + pipe;
- horizontal lockup: `EggPipe`;
- favicon: монограмма или яйцо;
- dark mode: светлое яйцо на тёмном фоне;
- один акцентный цвет — yolk или teal.

---

## 9. Открытые вопросы

1. Нужен ли отдельный бренд-гайд с логотипом и палитрой?
2. Проверить товарный знак и поисковую выдачу.
3. Переименование пакета/import `metadata_generator` → `eggpipe` — выполнено.
