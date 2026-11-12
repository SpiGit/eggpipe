# Руководство по плагинам

Плагины подключаются двумя способами:

- установленный пакет с entry point (production/editable install);
- локальный Python-файл через `--plugin` (dev, v0.3+).

## GeneratorPlugin

```python
from typing import ClassVar, Literal

from metadata_generator import Artifact, GenerationResult, GeneratorInput, GeneratorPlugin


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
- `input_formats`: `None` — любой формат; `set` — перечисленные форматы и их наследники.
- Вход immutable: `model` — замкнутый `ModelSlice`, `context` — `GenerationContext`, `config` — блок генератора из `.mg.yaml`.
- Формат каждой сущности — `entity.format` / `entity.format_version`; сводка — `context.formats`.
- Плагин **не пишет файлы**; он возвращает `Artifact`.
- `Artifact.path` — относительный POSIX-путь; `content` — UTF-8, LF, без BOM.
- Ошибки — структурированные `Diagnostic`, не строки.
- Если `GenerationResult.errors` непустой, артефакты этого генератора отбрасываются.
- Исключение из `generate()`/`validate_config()` не останавливает другие генераторы.

### Entry point

```toml
[project.entry-points."metadata_generator.generators"]
my-generator = "my_package.plugins:MyGenerator"
```

```bash
pip install -e ./my-generator
mg gen list
mg generate -g my-generator
```

### Локальная разработка

```bash
mg generate --plugin ./my_plugin.py
```

Модуль загружается через `importlib.util`; `sys.path` не меняется. В файле достаточно класса
`GeneratorPlugin` с `id` и `api_version = "1"`.

## FormatPlugin

Формат, расширяющий `entity-model`, наследует `EntityModelFormat` и переопределяет hooks:

```python
from metadata_generator import EntityModelFormat


class SqlModelFormat(EntityModelFormat):
    format_names = ["sql-model"]
    supported_versions = ["1.0"]
    extends = "entity-model"
    primitive_types = {"string", "integer", "decimal", "timestamp"}
    layer_model = SqlLayer
    full_model = SqlModel

    def parse_extensions(self, document, raw) -> None:
        ...

    def validate_extensions(self, document):
        return []
```

```toml
[project.entry-points."metadata_generator.formats"]
sql-model = "my_package.formats:SqlModelFormat"
```

- `format` в YAML должен совпадать с `format_names`; в `.mg.yaml` формат не задаётся.
- `entity-model` зарезервирован ядром.
- `extends` — одиночное наследование; цикл/глубина > 10 — MG034.
- `B extends A` — B надмножество A; переименование/удаление полей A запрещено.
- `primitive_types` наследуются; можно добавлять свои.
- `layer_model` валидирует слой, `full_model` — итоговую модель после merge.
- Для списков формат объявляет `MergePolicy` через `json_schema_extra`:
  `KEYED` (по `name`), `APPEND`, `UNION`, `ERROR`. По умолчанию core-списки — `KEYED`,
  неизвестные списки — `ERROR`.
- Генератор для базового формата принимает наследников через `input_formats`.
- `mg format list` показывает зарегистрированные форматы.

## Контекст генерации

`GenerationContext` содержит:

- `variables` — `--var` и `variables` из `.mg.yaml` (CLI > config);
- `naming_hint` — подсказка `defaults.naming_convention`, не приказ переименовывать;
- `imports` — resource-файлы по alias;
- `sources` — пути source-документов;
- `formats` — сводка форматов запуска; формат конкретной сущности — `entity.format`;
- `format` / `format_version` — deprecated, `None` в смешанном запуске;
- `run_id`, `config_dir`.

## Шаблоны

Ядро не предоставляет шаблонизатор: движок выбирает плагин (ТЗ §7). Для Jinja2 доступен
опциональный helper `metadata_generator.templating` (extra `[jinja]`):

```bash
pip install "metadata-generator[jinja]"
```

```python
from metadata_generator.templating import jinja_environment, render_template

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
from metadata_generator import git_provenance

provenance = git_provenance(entity.source) if entity.source else None
```

`git_provenance` возвращает commit hash и дату последнего коммита файла. Значения не попадают
в артефакты автоматически — это решение генератора.

## Версионирование

`api_version` повышается только при breaking change контракта. Несовместимый плагин не ломает
запуск, если не выбран; явно выбранный несовместимый плагин — exit 2.

## Проверка

- `mg gen list` / `mg gen info <id>`;
- `mg format list`;
- contract-тесты: `GeneratorInput`/`GenerationResult`/`Diagnostic`;
- golden-тест через reference-плагин.
