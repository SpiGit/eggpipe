# Модели данных

## ModelDocument

Один YAML-файл: `format`, `version`, `path`, `imports`, `model`, `metadata`.

## SourceModel

Результат композиции источников и импортов. Содержит `entities`, `enums`, `types`,
`name`, `description`, `metadata`.

## ModelSlice

Замкнутый срез для генератора. Те же коллекции, что у `SourceModel`, плюс:

```python
slice.formats -> frozenset[FormatInfo]
```

## Entity

```python
Entity(
    name: str,
    description: str | None,
    version: str | int | None,
    updated_at: date | datetime | None,
    extends: str | ExtendsRef | None,
    fields: tuple[FieldDef, ...],
    metadata: dict[str, Any],
    source: Path | None,          # исключён из сериализации
    format: str | None,           # исключён из сериализации
    format_version: str | None,   # исключён из сериализации
    layer_sources: tuple[Path, ...],
)
```

## FieldDef

```python
FieldDef(
    name: str,
    type: str,
    description: str | None,
    required: bool = False,
    nullable: bool = False,
    default: DefaultValue | UNSET = UNSET,
    constraints: Constraints | None,
    metadata: dict[str, Any],
    source: Path | None,
)
```

`UNSET` отличается от `default: null`. `constraints`: `min`, `max`, `min_length`,
`max_length`, `pattern`.

## EnumDef / CustomType

`EnumDef` содержит `values: tuple[EnumValue, ...]`.
`CustomType` содержит `base` и опциональные `constraints`.

## Служебные типы

- `FormatInfo(name, version)` — конкретный формат и версия.
- `FormatSchema(layer_entity, full_entity)`.
- `MergePolicy`: `KEYED`, `APPEND`, `UNION`, `ERROR`.
- `Diagnostic(level, code, message, location)`.
- `EntityIdentity(name)`, `FieldIdentity(name)` — identity для дельта-моделей.
- `Provenance(path, commit, date)`.

## Инъекция

В `@generator` можно принимать только `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
Другие типы дают MG302.
