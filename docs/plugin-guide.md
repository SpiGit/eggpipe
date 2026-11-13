# Руководство по плагинам

Плагины подключаются двумя способами:

- установленный пакет с entry point (production/editable install);
- локальный Python-файл через `--plugin` (dev, v0.3+).

## Генератор через декоратор

Основной способ:

```python
from eggpipe import Artifact, GeneratorConfig, GenerationContext, ModelSlice, generator


@generator(id="my-generator", input_formats={"entity-model"})
def my_generator(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    names = [entity.name for entity in model.entities]
    return [Artifact(path="entities.txt", content="\n".join(names) + "\n")]
```

- `id` опционален: по умолчанию имя функции с `_` → `-`.
- `input_formats` обязателен.
- Аргументы инжектятся по аннотациям: `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
- Возврат: `GenerationResult`, `Artifact`, `list[Artifact]` или `tuple[Artifact, ...]`.
- Entry point указывает на функцию:
  ```toml
  [project.entry-points."eggpipe.generators"]
  my-generator = "my_package.plugins:my_generator"
  ```

## GeneratorPlugin (advanced)

```python
from typing import ClassVar, Literal

from eggpipe import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin


class MyGenerator(GeneratorPlugin):
    api_version: ClassVar[Literal["1"]] = "1"
    id = "my-generator"
    name = "My Generator"
    input_formats = {"entity-model"}   # None = любой формат

    def generate(self, input: GeneratorInput) -> GenerationResult:
        names = [entity.name for entity in input.model.entities]
        return GenerationResult(
            artifacts=[Artifact(path="entities.txt", content="\n".join(names) + "\n")]
        )
```

Правила:

- `id` совпадает с entry point id; `name` по умолчанию равен id.
- `input_formats` обязателен: `None` — любой формат, `set()` — ни один; иначе перечисленные
  форматы и их наследники. Несовместимость — MG033, exit 2, весь запуск без артефактов.
- Вход immutable: `model` — замкнутый `ModelSlice`, `context` — `GenerationContext`, `config` — блок генератора из `.eggpipe.yaml`.
- Формат каждой сущности — `entity.format` / `entity.format_version`; `context.formats` — форматы среза.
- Плагин **не пишет файлы**; он возвращает `Artifact`.
- `Artifact.path` — относительный POSIX-путь; `content` — UTF-8, LF, без BOM.
- Ошибки — структурированные `Diagnostic`, не строки.
- Если `GenerationResult.errors` непустой, артефакты этого генератора отбрасываются.
- Исключение из `generate()`/`validate_config()` не останавливает другие генераторы.

### Entry point

```toml
[project.entry-points."eggpipe.generators"]
my-generator = "my_package.plugins:MyGenerator"
```

```bash
pip install -e ./my-generator
eggpipe gen list
eggpipe generate -g my-generator
```

### Локальная разработка

```bash
eggpipe generate --plugin ./my_plugin.py
```

Модуль загружается через `importlib.util`; `sys.path` не меняется. В файле достаточно класса
`GeneratorPlugin` с `id` и `api_version = "1"`.

## FormatPlugin

Формат, расширяющий `entity-model`, наследует `EntityModelFormat` и переопределяет hooks:

```python
from eggpipe import PRIMITIVE_TYPES, EntityModelFormat, FormatSchema


class SqlModelFormat(EntityModelFormat):
    format_names = ["sql-model"]
    supported_versions = ["1.0"]
    extends = "entity-model"
    base_versions = {"1.0": "1.0"}   # sql-model 1.0 → entity-model 1.0
    primitive_types = PRIMITIVE_TYPES | {"decimal", "timestamp"}
    schemas = {
        "1.0": FormatSchema(
            layer_entity=SqlLayerEntity,
            full_entity=SqlEntity,
        )
    }

    def parse_extensions(self, document, raw) -> None:
        ...

    def validate_extensions(self, document):
        return []
```

```toml
[project.entry-points."eggpipe.formats"]
sql-model = "my_package.formats:SqlModelFormat"
```

- `format` в YAML должен совпадать с `format_names`; в `.eggpipe.yaml` формат не задаётся.
- `entity-model` зарезервирован ядром.
- `extends` — одиночное наследование; цикл/глубина > 10 — MG034.
- `B extends A` — B надмножество A; переименование/удаление полей A запрещено.
- `supported_versions` — упорядоченный список; нет `version` в YAML — берётся последняя.
- `base_versions[B_version] = A_version`; версии форматов независимы.
- `schemas[version]` содержит `layer_entity`/`full_entity`.
- `primitive_types` наследуются; можно добавлять свои.
- `layer_entity` валидирует слой, `full_entity` — итоговую сущность после merge.
- Дельта-модели наследуют `EntityIdentity`/`FieldIdentity`; полные — `Entity`/`FieldDef`.
- Обязательность новых полей определяет формат: partial в слое, complete в итоге.
- Документ остаётся общим конвертом; first-class document-level поля — future, в v2.1 через `metadata`.
- Для списков формат объявляет `MergePolicy` через `json_schema_extra`:
  - `KEYED` — патч существующих + новые (`fields`);
  - `APPEND` — только новые (`types`, `enums`, `enum.values`);
  - `UNION` — уникальные скаляры;
  - `ERROR` — фиксированный кортеж.
  По умолчанию неизвестные списки — `ERROR`.
- Генератор для базового формата принимает наследников через `input_formats`.
- `eggpipe format list` показывает зарегистрированные форматы.

## Контекст генерации

`GenerationContext` содержит:

- `variables` — `--var` и `variables` из `.eggpipe.yaml` (CLI > config);
- `naming_hint` — подсказка `defaults.naming_convention`, не приказ переименовывать;
- `imports` — resource-файлы по alias; top-level `resources` и `models.<dir>.resources` попадают сюда же.
- `sources` — пути source-документов;
- `formats` — `frozenset` форматов среза; формат конкретной сущности — `entity.format`;
- `run_id`, `config_dir`.

## Шаблоны

Ядро не предоставляет шаблонизатор: движок выбирает плагин (ТЗ §7). Для Jinja2 доступен
опциональный helper `eggpipe.templating` (extra `[jinja]`):

```bash
pip install "eggpipe[jinja]"
```

```python
from eggpipe.templating import jinja_environment, render_template

environment = jinja_environment(
    package="my_generator",             # шаблоны внутри wheel: my_generator/templates/
    templates_dir=config.options.get("templates_dir"),
    config_dir=input.context.config_dir,
)
content = render_template(environment, "schema.sql.j2", entities=entities)
```

- helper только создаёт окружение (`PackageLoader` или `FileSystemLoader`,
  `StrictUndefined`) и превращает ошибки Jinja2 в `TemplateError`;
- `templates_dir` имеет приоритет над `package`; относительный путь разрешается от
  `config_dir`;
- отсутствие Jinja2, каталога или шаблона — `TemplateError`; генератор может отобразить
  её в `MG300`;
- `jinja2` не входит в основные зависимости и не импортируется ядром при старте.

TPC-H example использует этот helper и `options.templates_dir` для override.

## Provenance

`Entity.source` содержит путь к документу, из которого пришла сущность (заполняется парсером,
исключён из `model_dump`/JSON Schema). Для git-метаданных используйте:

```python
from eggpipe import git_provenance

provenance = git_provenance(entity.source) if entity.source else None
```

`git_provenance` возвращает commit hash и дату последнего коммита файла. Значения не попадают
в артефакты автоматически — это решение генератора.

## Версионирование

`api_version` повышается только при breaking change контракта. Несовместимый плагин не ломает
запуск, если не выбран; явно выбранный несовместимый плагин — exit 2.

## Проверка

- `eggpipe gen list` / `eggpipe gen info <id>`;
- `eggpipe format list`;
- contract-тесты: `GeneratorInput`/`GenerationResult`/`Diagnostic`;
- golden-тест через reference-плагин.
