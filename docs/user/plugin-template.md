# Шаблон плагина

## Первый плагин за 10 минут

Шаблон [copier](https://copier.readthedocs.io/) создаёт готовый пакет: генератор,
формат, entry points, contract-тесты и README. Контракты плагинов описаны в
[plugins.md](./plugins.md); ниже — короткий путь от генерации проекта до проверки.

### 1. Сгенерировать проект

```bash
git clone --depth 1 https://github.com/SpiGit/eggpipe.git
uvx copier@9.19.1 copy eggpipe/examples/plugin-template-copier my-plugin
```

Copier спросит `project_name`, `package_name`, `generator_id` и `description`.
Значения можно передать сразу:

```bash
uvx copier@9.19.1 copy eggpipe/examples/plugin-template-copier my-plugin \
  -d package_name=eggpipe_my_plugin -d generator_id=my-plugin
```

Исходник шаблона — [examples/plugin-template-copier](https://github.com/SpiGit/eggpipe/tree/main/examples/plugin-template-copier).

### 2. Структура проекта

```text
my-plugin/
  pyproject.toml
  README.md
  src/eggpipe_my_plugin/__init__.py
  tests/test_contract.py
```

`__init__.py` содержит:

- `TemplateFormat` — формат, наследующий `entity-model`;
- `my_plugin_generator` — генератор под `@generator` с `id="my-plugin"`.

### 3. Entry points

```toml
[project.entry-points."eggpipe.generators"]
"my-plugin" = "eggpipe_my_plugin:my_plugin_generator"

[project.entry-points."eggpipe.formats"]
"my-plugin-model" = "eggpipe_my_plugin:TemplateFormat"
```

Имя entry point генератора должно совпадать с его `id`, иначе плагин попадёт в
`warning` и не загрузится.

### 4. Модель и конфиг

`model.yaml` использует формат плагина:

```yaml
format: my-plugin-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
        - name: email
          type: string
```

`.eggpipe.yaml` подключает генератор:

```yaml
version: "1.0"
sources:
  - path: ./model.yaml
    layout: monolith
generators:
  - id: my-plugin
    output_dir: ./out
```

### 5. Проверить плагин

```bash
uv sync --extra dev
uv run eggpipe gen list
uv run eggpipe gen info my-plugin
uv run eggpipe format info my-plugin-model
uv run eggpipe generate
cat out/my-plugin.json
```

В `gen info` и `format info` проверь:

- `input_formats` содержит `entity-model` и `my-plugin-model`;
- `extends: entity-model` и `base_versions: 1.0->1.0` — формат наследует базовый;
- `module`/`class` показывают, откуда загружен плагин. У формата это пакет
  `eggpipe_my_plugin`, у генератора на decorator API — адаптер ядра
  (`eggpipe.interfaces.generator`): так работает `@generator`, это ожидаемо.

Если id указан с опечаткой, команда покажет ближайшие варианты и доступные плагины.

### 6. Запустить тесты

```bash
uv run pytest
```

Шаблонные тесты проверяют контракт генератора, результат генерации и регистрацию
формата в `FormatRegistry`. Используй их как основу для своего плагина.

## Ручной пример

Готовый шаблон генератора и формата без генерации: [examples/plugin-template](https://github.com/SpiGit/eggpipe/tree/main/examples/plugin-template).

```bash
pip install -e examples/plugin-template
eggpipe gen list
eggpipe format list
```

В списках появятся:

```text
template-json    Template JSON
template-model   versions=1.0
```

## Что показывает шаблон

- регистрацию генератора через `@generator`;
- регистрацию формата через entry points `eggpipe.formats`;
- наследование формата от `entity-model`;
- contract-тесты для `id`, `input_formats`, сигнатуры и результата;
- правило «плагин возвращает `Artifact`, ядро пишет файлы».

## Contract-тесты

```bash
uv run pytest examples/plugin-template/tests
```

Тесты проверяют контракт генератора и регистрацию формата. Используй их как основу
для своего плагина.
