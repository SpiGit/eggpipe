# Format API

## FormatPlugin

```python
from typing import ClassVar, Literal

from eggpipe import EntityModelFormat, FormatSchema


class MyFormat(EntityModelFormat):
    api_version: ClassVar[Literal["1"]] = "1"
    format_names: ClassVar[list[str]] = ["sql-model"]
    supported_versions: ClassVar[list[str]] = ["1.0"]
    extends: ClassVar[str | None] = "entity-model"
    base_versions: ClassVar[dict[str, str]] = {"1.0": "1.0"}
    primitive_types: ClassVar[set[str]] = {...}
    schemas: ClassVar[dict[str, FormatSchema]] = {...}

    def parse_extensions(self, document, raw) -> None: ...
    def validate_extensions(self, document) -> list[Diagnostic]: ...
```

`EntityModelFormat` — база для форматов, расширяющих `entity-model`. Она предоставляет
`parse`/`validate`; расширение переопределяет `parse_extensions`/`validate_extensions`.

## FormatSchema

```python
class FormatSchema:
    layer_entity: type[BaseModel]   # один слой
    full_entity: type[BaseModel]    # итоговая сущность
```

- `layer_entity` может быть partial.
- `full_entity` расширения наследует `full_entity` базовой версии.
- `schemas` содержит запись для каждой версии из `supported_versions`.

## Версии и наследование

```python
class PostgresFormat(EntityModelFormat):
    format_names = ["postgres-model"]
    supported_versions = ["2.0"]
    extends = "entity-model"
    base_versions = {"2.0": "1.0"}
```

- Версии форматов независимы.
- `base_versions[B_version] = A_version`.
- Нет `version` в YAML — берётся последняя из `supported_versions`.
- Цикл/глубина > 10, неверная база, конфликт схем/примитивов — MG034.
- Неизвестная версия — MG008.
- `entity-model` зарезервирован.

## Entry point

```toml
[project.entry-points."eggpipe.formats"]
postgres-model = "my_package.formats:PostgresFormat"
```

## Совместимость генератора

Генератор с `input_formats={"entity-model"}` принимает `postgres-model`, если тот
транзитивно наследует `entity-model`. Exact-only режима нет.
