# Каталог диагностик

Коды стабильны. Диапазоны: MG0xx — документ/YAML/формат, MG1xx — модель, MG2xx — композиция
и срезы, MG3xx — конфигурация и plugin API, MG4xx — запись артефактов, MG5xx — cleanup/manifest.

Статус указан для текущей реализации; часть проверок появится вместе со следующими слоями.

| Код | Уровень | Фаза | Проверка | Статус |
|-----|---------|------|----------|-------------|
| MG000 | error | parse | Синтаксис YAML, duplicate keys, multi-document, не-dict корень | реализовано |
| MG001 | — | validate | Зарезервирован; не эмитируется | неизвестный тип даёт MG004 |
| MG002 | error | composition | Дубликаты имён entity/enum/type после композиции | реализовано |
| MG003 | error | validate | Дубликат имени поля в entity | реализовано |
| MG004 | error | validate | Тип не входит в primitive_types и не является enum/type | реализовано |
| MG005 | error | validate | Некорректный regex в `constraints.pattern` | реализовано |
| MG006 | error | composition | Циклические импорты / глубина > 10 | реализовано |
| MG007 | error | parse | `format` отсутствует / неизвестен | реализовано |
| MG008 | error | parse | `version` не поддерживается | реализовано |
| MG009 | error | composition | `extends` не найден / неоднозначен / цикл / глубина > 10 | реализовано |
| MG010 | error | validate | `nullable=false` + `default=null` | реализовано |
| MG011 | warning | validate | `required=true` + `nullable=true` | реализовано |
| MG012 | warning | validate | Entity.name не в PascalCase | реализовано |
| MG013 | warning | validate | Неиспользуемый enum/type | реализовано |
| MG014 | warning | validate | `updated_at` старше mtime файла (opt-in; file-per-model) | реализовано |
| MG015 | warning | validate | Пустой description у required-поля | реализовано |
| MG016 | error | validate | `default` не приводится к итоговому типу | реализовано |
| MG017 | error | validate | `default` нарушает constraints/enum | реализовано |
| MG018 | error | slice | Неизвестное имя в `input` | реализовано |
| MG019 | error | validate | Пустой enum / дубликат имени или значения | реализовано |
| MG020 | error | validate | Цикл `CustomType.base` / глубина > 10 | реализовано |
| MG021 | error | validate | Неприменимый или противоречивый constraint | реализовано |
| MG022 | error | composition | Импорт вне project root | реализовано |
| MG023 | error | discovery | YAML в `sources` не является документом модели | реализовано |
| MG024 | warning | discovery | Дубликат resolved-пути | реализовано |
| MG025 | error | composition | Дубликат alias `as` / отсутствует alias у resource | реализовано (parse) |
| MG026 | warning | validate | Case-insensitive коллизия имён | реализовано |
| MG027 | warning | discovery | Пустой каталог модели в `directory-per-model` | реализовано |
| MG028 | error | parse/validate | Имя не соответствует pattern | реализовано (Pydantic) |
| MG029 | error | layers | Некорректная цепочка слоёв / конфликт layer merge | реализовано |
| MG030 | warning | engine | Неподдерживаемый в текущем окружении режим; проигнорирован | реализовано |
| MG031 | error | layers | Файл-слой содержит не одну сущность | реализовано |
| MG032 | error | resources | Дубликат alias ресурса | реализовано |
| MG033 | error | engine | Генератор не поддерживает формат сущности | реализовано |
| MG034 | error | formats | Цикл/глубина наследования, неверный `base_versions`, конфликт схем/примитивов | реализовано |
| MG035 | warning | layers | Дельта не добавляет ничего | реализовано |
| MG036 | warning | discovery | Glob не нашёл ни одного файла/каталога | реализовано |
| MG037 | error | discovery | `models.<dir>` указывает на неизвестный каталог | реализовано |
| MG038 | error | discovery | Путь одновременно в `files` и `resources` | реализовано |
| MG300 | error | engine | Генератор/запись/check упали или обнаружен drift | реализовано |
| MG301 | error | plugin | Нарушен контракт генератора: нет `input_formats`, неверная сигнатура/return type | реализовано |
| MG302 | error | plugin | Неизвестный инжектируемый параметр декоратора | реализовано |
| MG040 | error | write | Некорректный artifact path / content | реализовано |
| MG041 | error | write | Ownership-конфликт / `on_conflict: error` | реализовано |
| MG042 | error | planning | Дубликат artifact path / case-collision / prefix-конфликт | реализовано |
| MG043 | warning | planning | `skip` для не-owned файла | реализовано |
| MG050 | warning | cleanup | Changed owned-файл не удалён | реализовано |
| MG051 | warning | cleanup | Stale generated location в глобальном manifest | реализовано |
| MG052 | error | manifest | Manifest повреждён или версия не поддерживается | реализовано |

## MG030

`MG030` — warning для режима, который невозможно применить в текущем окружении. Сейчас это
`cleanup: prompt` без поддерживаемого tty-подтверждения: ядро откатывается к `cleanup: off`.

`MG030` и `MG300` отражены в диапазонах ТЗ v2.0 §9.3.
Коды MG027, MG029, MG031–MG038, MG051, MG052, MG301, MG302 относятся к слоям, форматам,
ресурсам, manifest и decorator API и реализованы в v2.0.

`diagnostics.ignore` и `--ignore` игнорируют только warnings; errors показываются всегда.
