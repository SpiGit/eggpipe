# Быстрый старт

## 1. Установка

```bash
pip install eggpipe
```

Опционально:

```bash
pip install "eggpipe[watch]"   # eggpipe watch
pip install "eggpipe[jinja]"   # хелпер для Jinja2-плагинов
```

## 2. Создание конфигурации

```bash
eggpipe init --layout monolith
```

Будут созданы `.eggpipe.yaml` и пример `model.yaml`. Для других раскладок:

```bash
eggpipe init --layout file-per-model
eggpipe init --layout directory-per-model
```

## 3. Проверка модели

```bash
eggpipe model validate ./model.yaml
```

## 4. Генерация

```bash
eggpipe generate --plan      # показать план без записи
eggpipe generate             # сгенерировать артефакты
eggpipe generate --check     # проверить актуальность для CI
```

## 5. Просмотр результата

Артефакты пишутся в `output_dir` генератора. Ownership, хэши и locations хранятся в
`.eggpipe/manifest.json`.

```bash
eggpipe clean --dry-run
eggpipe clean --yes
```

## Минимальная модель

```yaml
format: entity-model
version: "1.0"
model:
  entities:
    - name: User
      fields:
        - name: id
          type: integer
          required: true
          description: Identifier
        - name: email
          type: string
          required: true
          description: Email
```

## Минимальный конфиг

```yaml
version: "1.0"
sources:
  - path: ./model.yaml
    layout: monolith
generators:
  - id: my-generator
    output_dir: ./generated
```

Без установленного генератора команда завершится config-ошибкой. Пример работающих
генераторов — TPC-H example в каталоге `examples/tpc-h` и [плагины](plugins.md).

## Дальше

- [Плагины](plugins.md) — как написать генератор или формат.
- [Диагностики](reference/diagnostics.md) — что означает код `MGxxx`.
- [AI context](../ai/context.md) — если документацию читает агент.
