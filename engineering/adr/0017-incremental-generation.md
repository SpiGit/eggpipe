# ADR-0017: Инкрементальная генерация

- **Статус:** принято
- **Дата:** 2026-11-16
- **Связанные документы:** [ТЗ v2.5 §10.7](../requirements/v2.5.md), [ADR-0004](./0004-ownership-manifest-cleanup.md), [ADR-0009](./0009-global-manifest-ownership.md), [Roadmap](../roadmap.md)

---

## 1. Контекст

Сейчас Eggpipe при каждом запуске заново:

- обнаруживает источники;
- парсит документы;
- строит композицию и валидирует модель;
- вызывает все включённые генераторы;
- сравнивает артефакты с файлами и пропускает запись неизменённых.

Последний пункт уже экономит запись, но не парсинг и не работу генераторов. На больших
моделях это заметно, особенно в watch-режиме.

Manifest уже хранит `eggpipe_version`, `plugin_version`, `formats` и хэши артефактов,
поэтому его можно расширить входным fingerprint без изменения формата артефактов.

## 2. Решение

Вводится **opt-in** инкрементальная генерация: `--incremental` / `EGGPIPE_INCREMENTAL=true`.

При включённом режиме Engine:

1. Выполняет discovery.
2. Считает fingerprint входа.
3. Проверяет manifest:
   - fingerprint совпадает;
   - `eggpipe_version` совпадает;
   - `plugin_version` каждого генератора совпадает;
   - все артефакты существуют и их `sha256` совпадают.
4. Если всё совпало — возвращает отчёт без парсинга, валидации и вызова генераторов.
5. Иначе выполняет полный путь и записывает новый fingerprint в manifest.

## 3. Fingerprint

Fingerprint — SHA-256 от:

- версии Eggpipe;
- `ProjectConfig` (sources, generators, variables, defaults, diagnostics);
- variables после CLI-override;
- содержимого source-документов и их input-closure через `FormatPlugin.input_paths`, рекурсивно;
- ресурсов: alias + содержимое;
- `plugin_version`, `api_version` и `input_formats` включённых генераторов;
- `__version__`, `api_version`, `extends`, `base_versions`, версий и primitive types форматов.

Fingerprint не учитывает:

- код плагина, если версия плагина не изменилась; для форматов версия — `__version__`,
  для генераторов — `plugin_version`.
- переменные окружения и другие внешние источники, влияющие на генератор.

Контракт зависимостей формата:

- `FormatPlugin.input_paths(raw, base_path)` объявляет файлы, которые плагин читает при парсинге.
- `base_path` — каталог документа, как в `parse`.
- `EntityModelFormat` возвращает `model.imports`.
- Возврат `None` означает, что формат не поддерживает контракт, и incremental отключается.

Плагин обязан быть детерминированным либо объявить все входные файлы.

## 4. Когда incremental отключается

Engine не использует кэш, если:

- `--incremental` не задан;
- `--check` (нужна реальная проверка drift);
- `--force`, `--clean` или CLI `--strict`;
- `diagnostics.stale_dates: true`;
- `allow_outside_imports: true`;
- source- или import-пути выходят за project root;
- manifest отсутствует или повреждён;
- набор locations в manifest не совпадает с конфигом;
- формат вернул `input_paths=None`;
- файл нельзя прочитать, YAML не парсится или путь небезопасен.

Причина отключения пишется в debug-лог и видна с `--verbose`.

`--plan` кэш использует: план тогда состоит из `skip`, потому что реальный `generate`
пропустил бы ту же работу.

## 5. Manifest

В `ManifestLocation` добавляется необязательное поле:

```json
"input_fingerprint": "<sha256 hex>"
```

Fingerprint хранится как hex-строка SHA-256 без префикса `sha256:` — так же, как
`sha256` артефактов в manifest. Поле optional: старые manifest v2 читаются без него.
Manifest v1 по-прежнему не поддерживается.

Полный прогон без incremental записывает `input_fingerprint: null`: следующий
incremental-запуск будет промахом и заполнит поле заново.

## 6. Отчёт

При попадании в кэш:

- `generators[].status = "skipped"`;
- `artifacts[].action = "skip"`;
- `timings.parse_ms`, `validate_ms`, `generate_ms`, `write_ms` равны `0`;
- `timings.discovery_ms` и `timings.fingerprint_ms` отражают реальную работу;
- глобальная сводка `formats` пуста: без парсинга модели число сущностей неизвестно;
- `cleanup` не запускается: все owned-артефакты текущего location совпадают.

## 7. Последствия

- Повторный запуск без изменений не парсит модель и не вызывает генераторы.
- `--check` всегда работает по реальным файлам.
- Ошибка в fingerprint может привести к устаревшим артефактам, поэтому режим opt-in
  и покрыт тестами инвалидации.
- Плагины должны bump `plugin_version` при изменении поведения.
- Manifest с `input_fingerprint` не читается более старой версией Eggpipe: поле новое,
  а `ManifestLocation` запрещает неизвестные поля. Для beta (ADR-0014) это допустимо.
- L2/L3 (кэш парсинга, per-entity) остаются future.
