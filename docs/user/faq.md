# FAQ

### Eggpipe пишет файлы сам?

Нет. Плагин возвращает `Artifact`; запись, ownership, manifest и lock — зона ядра.

### Можно ли использовать Eggpipe как библиотеку?

Да:

```python
rules = GeneratorRulesLoader().load(".eggpipe.yaml")
engine = Engine(AppConfig(), rules)
report = engine.generate()
```

`build()` и `check()` не пишут файлы. `Engine` не вызывает `sys.exit` и не настраивает
root-logger.

### Чем `@generator` отличается от `GeneratorPlugin`?

`@generator` — тонкий адаптер функции с инъекцией аргументов. Классовый API нужен для
состояния, `validate_config()` или сложной инициализации.

### Почему нужен `input_formats`?

Он определяет совместимость генератора с форматами сущностей. `None` — любой,
`set()` — ни один, набор — указанные форматы и наследники.

### Можно ли смешивать форматы в одном запуске?

Да. Каждая сущность несёт `Entity.format`; генератор проверяется против `input_formats`
до запуска. Несовместимость — MG033, exit 2.

### Где хранится ownership?

В `.eggpipe/manifest.json`. Ключ location — `(generator, output_dir)`, артефакты
хранятся с путём и sha256.

### Почему `--force` не перезаписал файл?

Файл принадлежит другому generator/location. `--force` работает только для unowned.
Сначала `eggpipe clean` или удалите старый manifest.

### Нужна ли миграция с v1.x?

Нет. Проект ещё не публиковался; v1.x — внутренняя история требований. Обратная совместимость
до первого публичного релиза не поддерживается, отдельный migration guide не нужен.

### Чем `--plan`, `--dry-run` и `--check` отличаются?

- `--plan`/`--dry-run` — показать план, ничего не писать.
- `--check` — проверить drift, exit 1 при расхождении, ничего не писать.
- `generate` без флагов — записать артефакты и обновить manifest.

### Почему watch не перезагружает плагины?

Плагины загружаются один раз. Для перезагрузки перезапустите `eggpipe watch`.
Конфиг перезагружается при изменении `.eggpipe.yaml`.

### Как добавить свой формат?

Унаследовать `EntityModelFormat`, задать `format_names`, `supported_versions`,
`extends`, `base_versions`, `primitive_types`, `schemas` и зарегистрировать entry point
`eggpipe.formats`. Подробнее — [Format API](api/format.md).

### Где искать код ошибки?

В [каталоге диагностик](reference/diagnostics.md) и через `rg "MGxxx" src tests`.
