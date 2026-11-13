# Каталог диагностик

Коды стабильны. Диапазоны: EG0xx — документ/YAML/формат, EG1xx — модель, EG2xx — композиция
и срезы, EG3xx — конфигурация и plugin API, EG4xx — запись артефактов, EG5xx — cleanup/manifest.

Статус указан для текущей реализации; часть проверок появится вместе со следующими слоями.

| Код | Уровень | Фаза | Проверка | Статус |
|-----|---------|------|----------|-------------|
| EG000 | error | parse | Синтаксис YAML, duplicate keys, multi-document, не-dict корень | реализовано |
| EG001 | — | validate | Зарезервирован; не эмитируется | неизвестный тип даёт EG004 |
| EG002 | error | composition | Дубликаты имён entity/enum/type после композиции | реализовано |
| EG003 | error | validate | Дубликат имени поля в entity | реализовано |
| EG004 | error | validate | Тип не входит в primitive_types и не является enum/type | реализовано |
| EG005 | error | validate | Некорректный regex в `constraints.pattern` | реализовано |
| EG006 | error | composition | Циклические импорты / глубина > 10 | реализовано |
| EG007 | error | parse | `format` отсутствует / неизвестен | реализовано |
| EG008 | error | parse | `version` не поддерживается | реализовано |
| EG009 | error | composition | `extends` не найден / неоднозначен / цикл / глубина > 10 | реализовано |
| EG010 | error | validate | `nullable=false` + `default=null` | реализовано |
| EG011 | warning | validate | `required=true` + `nullable=true` | реализовано |
| EG012 | warning | validate | Entity.name не в PascalCase | реализовано |
| EG013 | warning | validate | Неиспользуемый enum/type | реализовано |
| EG014 | warning | validate | `updated_at` старше mtime файла (opt-in; file-per-model) | реализовано |
| EG015 | warning | validate | Пустой description у required-поля | реализовано |
| EG016 | error | validate | `default` не приводится к итоговому типу | реализовано |
| EG017 | error | validate | `default` нарушает constraints/enum | реализовано |
| EG018 | error | slice | Неизвестное имя в `input` | реализовано |
| EG019 | error | validate | Пустой enum / дубликат имени или значения | реализовано |
| EG020 | error | validate | Цикл `CustomType.base` / глубина > 10 | реализовано |
| EG021 | error | validate | Неприменимый или противоречивый constraint | реализовано |
| EG022 | error | composition | Импорт вне project root | реализовано |
| EG023 | error | discovery | YAML в `sources` не является документом модели | реализовано |
| EG024 | warning | discovery | Дубликат resolved-пути | реализовано |
| EG025 | error | composition | Дубликат alias `as` / отсутствует alias у resource | реализовано (parse) |
| EG026 | warning | validate | Case-insensitive коллизия имён | реализовано |
| EG027 | warning | discovery | Пустой каталог модели в `directory-per-model` | реализовано |
| EG028 | error | parse/validate | Имя не соответствует pattern | реализовано (Pydantic) |
| EG029 | error | layers | Некорректная цепочка слоёв / конфликт layer merge | реализовано |
| EG030 | warning | engine | Неподдерживаемый в текущем окружении режим; проигнорирован | реализовано |
| EG031 | error | layers | Файл-слой содержит не одну сущность | реализовано |
| EG032 | error | resources | Дубликат alias ресурса | реализовано |
| EG033 | error | engine | Генератор не поддерживает формат сущности | реализовано |
| EG034 | error | formats | Цикл/глубина наследования, неверный `base_versions`, конфликт схем/примитивов | реализовано |
| EG035 | warning | layers | Дельта не добавляет ничего | реализовано |
| EG036 | warning | discovery | Glob не нашёл ни одного файла/каталога | реализовано |
| EG037 | error | discovery | `models.<dir>` указывает на неизвестный каталог | реализовано |
| EG038 | error | discovery | Путь одновременно в `files` и `resources` | реализовано |
| EG300 | error | engine | Генератор/запись/check упали или обнаружен drift | реализовано |
| EG301 | error | plugin | Нарушен контракт генератора: нет `input_formats`, неверная сигнатура/return type | реализовано |
| EG302 | error | plugin | Неизвестный инжектируемый параметр декоратора | реализовано |
| EG040 | error | write | Некорректный artifact path / content | реализовано |
| EG041 | error | write | Ownership-конфликт / `on_conflict: error` | реализовано |
| EG042 | error | planning | Дубликат artifact path / case-collision / prefix-конфликт | реализовано |
| EG043 | warning | planning | `skip` для не-owned файла | реализовано |
| EG050 | warning | cleanup | Changed owned-файл не удалён | реализовано |
| EG051 | warning | cleanup | Stale generated location в глобальном manifest | реализовано |
| EG052 | error | manifest | Manifest повреждён или версия не поддерживается | реализовано |

## EG030

`EG030` — warning для режима, который невозможно применить в текущем окружении. Сейчас это
`cleanup: prompt` без поддерживаемого tty-подтверждения: ядро откатывается к `cleanup: off`.

`EG030` и `EG300` входят в диапазоны EG0xx и EG3xx.
Коды EG027, EG029, EG031–EG038, EG051, EG052, EG301, EG302 относятся к слоям, форматам,
ресурсам, manifest и decorator API.

`diagnostics.ignore` и `--ignore` игнорируют только warnings; errors показываются всегда.
