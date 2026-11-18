# ADR-0018: Per-entity генерация

- **Статус:** принято
- **Дата:** 2026-11-17
- **Связанные документы:** [ТЗ v2.4 §6.1.2, §8.2, §10](../requirements/v2.4.md), [ADR-0004](./0004-ownership-manifest-cleanup.md), [ADR-0009](./0009-global-manifest-ownership.md), [ADR-0017](./0017-incremental-generation.md)

---

## 1. Контекст

Сейчас `eggpipe generate` всегда строит полный `ModelSlice` и передаёт его каждому
включённому генератору. Для больших моделей это избыточно, когда нужно пересобрать
артефакты одной сущности: остальные сущности не менялись, но парсинг, композиция и
генерация выполняются целиком.

Нельзя просто отфильтровать `ModelSlice` для любого генератора: генератор с
combined-артефактом (общая SQL-схема, один TypeScript-файл) может зависеть от всех
сущностей. Запись такого частичного результата перезапишет общий артефакт и потеряет
данные других сущностей.

Нужен явный контракт: генератор сам объявляет, умеет ли он работать per-entity.

## 2. Решение

Вводится **opt-in** per-entity генерация:

- CLI: `eggpipe generate --entity User`, `--entity User,Post`.
- API: `Engine.build(entities=...)`, `Engine.generate(entities=...)`,
  `Engine.check(entities=...)`.
- `GeneratorPlugin.output_scope: ClassVar[Literal["model", "entity"]] = "model"`.
- `@generator(..., output_scope="entity")` для decorator API.

Per-entity режим разрешён, только если **все** выбранные генераторы объявили
`output_scope="entity"`. Иначе `EG303`, exit 2, артефакты не пишутся.

## 3. Семантика

- Выбор применяется после композиции, по именам итоговой модели.
- Неизвестное имя — `EG018`; пустой выбор в CLI — usage error (exit 2), в API — `EG018`.
- Срез замыкается по enums/types так же, как `generators[].input`.
- Формат сущности не меняется; проверка `input_formats` и `EG033` сохраняются.
- Генератор с `output_scope="entity"` обязан:
  - строить артефакты только из выбранных entities;
  - не зависеть от других entities;
  - использовать стабильные и уникальные пути артефактов для каждой entity.
- Ядро не проверяет уникальность путей между разными запусками; конфликты внутри запуска
  ловятся существующими EG042/EG041.

## 4. Manifest и cleanup

- Location остаётся `(generator, output_dir)`.
- Запись в per-entity режиме **дополняет** location: артефакты других entities сохраняются.
- Cleanup не выполняется, даже если `cleanup: enabled` или `--clean`; в v2.4 это сопровождается
  Warning EG030.
- Полный прогон или `eggpipe clean` реконсилируют manifest и удаляют сирот.
- `on_conflict` и `--force` действуют как обычно.

## 5. Incremental и watch

- `--entity` с `--incremental` не использует кэш и не обновляет `input_fingerprint`.
- `watch --entity` в v2.4 не поддерживается: usage error, exit 2.
- Per-entity watch и per-entity fingerprint — future.

## 6. Диагностика

- `EG303` — генератор не поддерживает per-entity output (`output_scope="model"`).
- `EG018` — неизвестное имя entity в `--entity`.
- `EG033` — формат сущности не принимается генератором (существующий код).

## 7. Последствия

- Генераторы без `output_scope="entity"` продолжают работать как раньше.
- Per-entity режим безопасен для combined-генераторов: они не могут случайно получить
  частичный срез.
- Автор per-entity генератора обязан обеспечить уникальные пути и отсутствие зависимостей
  от других entities.
- Manifest может временно содержать артефакты удалённых entities до полного прогона.
- Incremental и watch не ускоряют per-entity сценарий в v2.4.

## 8. Альтернативы

- **Фильтровать срез для любого генератора** — отклонено: ломает combined-артефакты.
- **Отдельные locations на entity** — отклонено в v1: меняет ownership и усложняет
  manifest; можно вернуться при per-entity watch.
- **Кэш на уровне entity** — отложено до L2/L3.
