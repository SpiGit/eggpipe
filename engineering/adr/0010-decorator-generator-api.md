# ADR-0010: Decorator API для генераторов

- **Статус:** принято
- **Дата:** 2026-11-12
- **Связанные документы:** [ТЗ v1.4 §6.1.1](../requirements/v1.4.md), [ADR-0005](./0005-library-api.md), [System Design §2.4](../system-design/index.md)
- **Актуальность:** ссылки на v1.4 исторические; действующие контракты — [ТЗ v2.2](../requirements/v2.2.md).

---

## 1. Контекст

Классовый `GeneratorPlugin` требует boilerplate: класс, `api_version`, `id`, `name`,
`input_formats`, метод `generate`. Для большинства генераторов это лишнее.
Нужен API в стиле Typer/FastAPI/Airflow: декоратор + функция + инъекция зависимостей.

## 2. Решение

Основной способ объявления генератора:

```python
@generator(id="tpch", input_formats={"entity-model"})
def tpch(
    model: ModelSlice,
    context: GenerationContext,
    config: GeneratorConfig,
) -> list[Artifact]:
    ...
```

- `@generator` создаёт класс-адаптер `GeneratorPlugin` и регистрирует его.
- `id` по умолчанию — имя функции с `_` → `-`.
- `name` по умолчанию — human-readable имя.
- `input_formats` обязателен.
- `api_version` по умолчанию `"1"`.
- Аргументы инжектятся по аннотациям: `ModelSlice`, `GenerationContext`, `GeneratorConfig`.
- Неизвестная аннотация — ошибка plugin contract.
- Возврат: `GenerationResult`, `Artifact`, `list[Artifact]`, `tuple[Artifact, ...]`.
- Entry point указывает на декорированную функцию.
- Проверка сигнатуры — при загрузке плагина, а не при импорте модуля.
- Классовый API остаётся advanced-вариантом.

## 3. Последствия

- Меньше boilerplate в плагинах.
- Функции легко тестировать напрямую.
- `mg gen list/info` работают через класс-адаптер.
- Нужна валидация сигнатуры и return type.
- Публичный API получает `generator`.

## 4. Альтернативы

- Только классовый API — отклонено: слишком много boilerplate.
- Декоратор, возвращающий функцию без класса-адаптера — отклонено: ломает entry points
  и `api_version`.
- Инъекция по именам аргументов — отклонено: менее надёжно, чем по аннотациям.
- Async-генераторы — отложено: движок синхронный.
