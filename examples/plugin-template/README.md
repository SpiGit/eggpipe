# Plugin template

Минимальный рабочий плагин Eggpipe: генератор и формат. Используй его как основу
для своего плагина или как референс для contract-тестов.

## Что внутри

```text
examples/plugin-template/
├── pyproject.toml
├── src/eggpipe_plugin_template/
│   └── __init__.py
└── tests/
    └── test_contract.py
```

- `TemplateFormat` — формат `template-model`, наследник `entity-model`;
- `template_generator` — генератор `template-json`, пишет `template.json`;
- `tests/test_contract.py` — проверки `id`, `input_formats`, сигнатуры и результата.

## Установка

Из корня репозитория:

```bash
pip install -e examples/plugin-template
```

Или через `uv`:

```bash
uv pip install -e examples/plugin-template
```

## Проверка

```bash
eggpipe gen list
eggpipe format list
```

В списках должны появиться:

```text
template-json    Template JSON
template-model   versions=1.0
```

## Пример проекта

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

## Contract-тесты

```bash
uv run pytest examples/plugin-template/tests
```

Тесты проверяют:

- корректный `id` и `input_formats`;
- валидность сигнатуры генератора;
- успешную генерацию артефакта;
- регистрацию формата и наследование от `entity-model`.

## Что менять под свой плагин

1. Переименуй пакет и entry points в `pyproject.toml`.
2. Замени `TemplateFormat` на свой формат или удали его, если формат не нужен.
3. Замени `template_generator` на свою логику.
4. Обнови contract-тесты под свой `id`, формат и артефакты.
5. Добавь README с примером использования.

## Ограничения

- Плагин не пишет файлы сам: он возвращает `Artifact`, запись делает ядро.
- `input_formats` обязателен: `None` — любой формат, `set()` — ни один.
- Ошибки контракта видны как `EG301`/`EG302`; ошибки генератора — `EG300`.
- Для публичного пакета добавь `eggpipe` в зависимости и `py.typed`, если нужен typing.
