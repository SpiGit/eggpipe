# Каталог диагностик

Коды стабильны. Диапазоны: MG0xx — документ/YAML/формат, MG1xx — модель, MG2xx — композиция
и срезы, MG3xx — конфигурация и plugin API, MG4xx — запись артефактов, MG5xx — cleanup.

Статус указан для ядра v0.1; часть проверок появится вместе со следующими слоями.

| Код | Уровень | Фаза | Проверка | Статус v0.1 |
|-----|---------|------|----------|-------------|
| MG000 | error | parse | Синтаксис YAML, duplicate keys, multi-document, не-dict корень | реализовано |
| MG001 | error | validate | Ссылка на несуществующий enum/type | зарезервирован; неизвестный тип даёт MG004 |
| MG002 | error | composition | Дубликаты имён entity/enum/type после композиции | реализовано |
| MG003 | error | validate | Дубликат имени поля в entity | реализовано |
| MG004 | error | validate | Тип не входит в primitive_types и не является enum/type | реализовано |
| MG005 | error | validate | Некорректный regex в `constraints.pattern` | реализовано |
| MG006 | error | composition | Циклические импорты / глубина > 10 | v0.2 |
| MG007 | error | parse | `format` отсутствует / неизвестен / смешаны форматы | реализовано |
| MG008 | error | parse | `version` отсутствует / не поддерживается | реализовано |
| MG009 | error | composition | `extends` не найден / неоднозначен / цикл / глубина > 10 | v0.2 |
| MG010 | error | validate | `nullable=false` + `default=null` | реализовано |
| MG011 | warning | validate | `required=true` + `nullable=true` | реализовано |
| MG012 | warning | validate | Entity.name не в PascalCase | реализовано |
| MG013 | warning | validate | Неиспользуемый enum/type | реализовано |
| MG014 | warning | validate | `updated_at` старше mtime файла (opt-in) | v0.2 |
| MG015 | warning | validate | Пустой description у required-поля | реализовано |
| MG016 | error | validate | `default` не приводится к итоговому типу | реализовано |
| MG017 | error | validate | `default` нарушает constraints/enum | реализовано |
| MG018 | error | slice | Неизвестное имя в `input` | реализовано |
| MG019 | error | validate | Пустой enum / дубликат имени или значения | реализовано |
| MG020 | error | validate | Цикл `CustomType.base` / глубина > 10 | реализовано |
| MG021 | error | validate | Неприменимый или противоречивый constraint | реализовано |
| MG022 | error | composition | Импорт вне project root | v0.2 |
| MG023 | error | discovery | YAML в `sources` не является документом модели | v0.2 |
| MG024 | warning | discovery | Дубликат resolved-пути | v0.2 |
| MG025 | error | composition | Дубликат alias `as` / отсутствует alias у resource | реализовано (parse) |
| MG026 | warning | validate | Case-insensitive коллизия имён | реализовано |
| MG028 | error | parse/validate | Имя не соответствует pattern | реализовано (Pydantic) |
| MG030 | warning | validate | Функция появится в следующей версии; проигнорирована | реализовано |
| MG300 | error | engine | Генератор/запись/check упали или обнаружен drift | реализовано |
| MG040 | error | write | Некорректный artifact path / content | реализовано |
| MG041 | error | write | Ownership-конфликт / `on_conflict: error` | реализовано |
| MG042 | error | planning | Дубликат artifact path / case-collision | реализовано |
| MG043 | warning | planning | `skip` для не-owned файла | реализовано |
| MG050 | warning | cleanup | Changed owned-файл не удалён | v0.2 |

## MG030

`MG030` — временный код для функций, которые ещё не реализованы в текущем этапе (в v0.1 это
`imports` и `entity.extends`). Это warning, а не тихий пропуск: функция игнорируется, а пользователь
видит сообщение.
