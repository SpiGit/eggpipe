# Cookbook

Короткие рецепты для типовых задач.

## Свой генератор за 5 минут

```python
from eggpipe import Artifact, GeneratorConfig, ModelSlice, generator


@generator(id="schema-json", input_formats={"entity-model"})
def schema_json(model: ModelSlice, config: GeneratorConfig) -> list[Artifact]:
    return [Artifact(path="schema.json", content="{}")]
```

```toml
[project.entry-points."eggpipe.generators"]
schema-json = "my_package.plugins:schema_json"
```

Подробнее: [Generator API](../api/generator.md).

## Свой формат

```python
from eggpipe import EntityModelFormat, FormatSchema


class PostgresFormat(EntityModelFormat):
    format_names = ["postgres-model"]
    supported_versions = ["1.0"]
    extends = "entity-model"
    base_versions = {"1.0": "1.0"}
    primitive_types = set(PRIMITIVE_TYPES) | {"decimal"}
    schemas = {"1.0": FormatSchema(layer_entity=LayerEntity, full_entity=PostgresEntity)}
```

Подробнее: [Format API](../api/format.md).

## Directory-per-model

```yaml
sources:
  - path: ./models
    layout: directory-per-model
    model_dirs: ["*"]
    files: ["*.yaml"]
```

```text
models/
  customer/
    base.yaml
    postgres.yaml
```

Базовый слой — `full_entity`, дельты — `layer_entity`, итог — `full_entity` производного
формата. Подробнее: [Конфигурация](../configuration.md).

## Ресурсы

```yaml
resources:
  - path: ./shared/templates
  - path: ./shared/fixtures/seed.json
    as: seed
```

В плагине:

```python
seed = context.imports["seed"].text()
```

## CI

```bash
eggpipe generate --check
```

Exit code 1 означает drift или отсутствующие файлы. Для полной проверки перед CI:

```bash
eggpipe config validate
eggpipe generate --plan
eggpipe generate --check
```

## Watch

```bash
pip install "eggpipe[watch]"
eggpipe watch --debounce-ms 300
```

Изменение конфига перезагружает настройки; плагины не перезагружаются.

## Cleanup

```bash
eggpipe clean --dry-run
eggpipe clean --yes
```

Удаляются только unchanged owned-файлы. Изменённые вручную остаются с MG050.
