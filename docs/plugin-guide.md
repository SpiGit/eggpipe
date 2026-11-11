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

    def generate(self, input: GeneratorInput) -> GenerationResult:
        names = [entity.name for entity in input.model.entities]
        return GenerationResult(
            artifacts=[Artifact(path="entities.txt", content="\n".join(names) + "\n")]
        )
```

Правила:

- `id` совпадает с entry point id; `name` по умолчанию равен id.
- Вход immutable: `model` — замкнутый `ModelSlice`, `context` — `GenerationContext`, `config` — блок генератора из `.mg.yaml`.
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
    primitive_types = {"string", "integer", "decimal", "timestamp"}

    def parse_extensions(self, document, raw) -> None:
        ...

    def validate_extensions(self, document):
        return []
```

```toml
[project.entry-points."metadata_generator.formats"]
sql-model = "my_package.formats:SqlModelFormat"
```

- `format` в YAML должен совпадать с `format_names`.
- `entity-model` зарезервирован ядром.
- `primitive_types` формата используется валидатором.
- Дополнительные поля складываются в `metadata[<format>]`.
- `mg format list` показывает зарегистрированные форматы.

## Контекст генерации

`GenerationContext` содержит:

- `variables` — `--var` и `variables` из `.mg.yaml` (CLI > config);
- `naming_hint` — подсказка `defaults.naming_convention`, не приказ переименовывать;
- `imports` — resource-файлы по alias;
- `sources` — пути source-документов;
- `format`, `format_version`, `run_id`, `config_dir`.

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
