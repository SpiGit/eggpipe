# Шаблон плагина

## Одна команда: copier

```bash
git clone --depth 1 https://github.com/SpiGit/eggpipe.git
uvx copier@9.19.1 copy eggpipe/examples/plugin-template-copier my-plugin
```

Copier спросит имя проекта, package name, generator id и описание; можно передать их
сразу через `-d package_name=... -d generator_id=...`. После генерации:

```bash
cd my-plugin
uv sync --extra dev
uv run pytest
```

Шаблон создаёт `pyproject.toml`, пакет, contract-тесты, entry points и README.
Исходник шаблона — [examples/plugin-template-copier](https://github.com/SpiGit/eggpipe/tree/main/examples/plugin-template-copier).

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

## Пример

`.eggpipe.yaml`:

```yaml
version: "1.0"
sources:
  - path: ./model.yaml
    layout: monolith
generators:
  - id: template-json
    output_dir: ./out
```

`model.yaml`:

```yaml
format: template-model
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

Запуск:

```bash
eggpipe generate
cat out/template.json
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
