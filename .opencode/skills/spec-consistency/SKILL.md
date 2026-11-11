---
name: spec-consistency
description: Проверка согласованности документов metadata-generator — термины, контракты, коды MGxxx, CLI и версии
---

# Проверка согласованности документации

Используй этот skill перед выпуском версии ТЗ, после крупных правок документации и при ревью.
Цель — найти расхождения между ТЗ, System Design, ADR и README.

## Порядок

1. Прочитай `AGENTS.md` и определи актуальную версию в `docs/requirements/index.md`.
2. Прочитай актуальное ТЗ, System Design, ADR-0001, README и `.session-context.md`.
3. Пройди чек-лист ниже. Для каждой находки зафиксируй `file:line`.
4. Ничего не исправляй без отдельного разрешения: сначала отчёт.

## Чек-лист

### Термины и модель

- [ ] Этапы: `ModelDocument` → `SourceModel` → `ModelSlice`; нет старых `Field`/`Enum` вместо `FieldDef`/`EnumDef`.
- [ ] `imports` находятся на уровне документа, а не сущности.
- [ ] `UNSET` явно отличается от `default: null`; null-матрица согласована (§3.6).
- [ ] `required_by_default` нигде не используется.
- [ ] `extends` допускает короткую форму и `{import, entity}`; область — import-closure.
- [ ] `metadata` есть у entity/field/enum/type/source; format-поля лежат под namespace формата.
- [ ] `constraints` описаны у поля и `CustomType`.

### Форматы и плагины

- [ ] `format` и `version` обязательны; один запуск — один формат.
- [ ] Публичный API совпадает с ТЗ §6.2 и System Design §2 (имена и состав).
- [ ] `api_version: ClassVar[Literal["1"]]`; поведение несовместимого плагина описано одинаково.
- [ ] `GeneratorInput` immutable; `AppConfig` плагину не передаётся.
- [ ] `GenerationResult.errors` отбрасывает артефакты только этого генератора.
- [ ] `Artifact.path` — относительный POSIX-путь; `content` — UTF-8, LF, без BOM.

### Композиция и срезы

- [ ] `sources[].input` фильтрует свой source; `generators[].input` применяется к union.
- [ ] Финальный срез замыкается по enums/types; неизвестное имя — `MG018`.
- [ ] Импорты ограничены project root; есть `--allow-outside-imports`.
- [ ] Discovery: `**/*.yaml` и `**/*.yml`, лексикографический порядок; пропускаются скрытые
      файлы/каталоги, `.git`, `.mg`, `__pycache__`, `.venv`, `node_modules` и все `output_dir`.
- [ ] Дубли resolved-путей обрабатываются один раз (`MG024`).

### CLI и диагностика

- [ ] Команды: `generate`, `watch`, `init`, `clean`; sub-apps `config`, `model`, `gen`, `format`.
- [ ] Флаги совпадают: `--plan`, `--check`, `--dry-run`, `--force`, `--yes`,
      `--include-disabled`, `--allow-outside-imports`, `--output-format`, `--var`,
      `--ignore`, `--show-secrets`.
- [ ] `--format` не существует как имя CLI-флага; вывод управляется `--output-format`.
- [ ] Exit codes: 0 — успех, 1 — errors/drift/strict, 2 — config/usage, 130 — Ctrl+C.
- [ ] Коды `MGxxx` не переиспользованы. Известное расхождение: таблица диапазонов §9.3 не совпадает
      с фактическими кодами §9.1; не считай это новой находкой, проверяй только переиспользование.
- [ ] `--plan`/`--dry-run` не создают каталоги и не берут write-lock; `--check` не пишет файлы
      и не обновляет манифест.

### Запись артефактов

- [ ] Ownership: перезапись и удаление только owned-файлов; чужие — `MG041` / `--force`.
- [ ] Manifest: `output_dir/.mg/manifests/<generator-id>.json`, пишется последним.
- [ ] `on_conflict: overwrite | skip | error`; `skip` не захватывает чужие файлы (`MG043`).
- [ ] `cleanup` по умолчанию `off`; удаляются только неизменённые owned-файлы.
- [ ] `skipped: true` не удаляется; failed generator не управляет cleanup.
- [ ] Валидация путей: POSIX, без `..`, NUL, backslash, reserved names; NFC; symlink (`MG040`).

### Версии и статусы

- [ ] В `docs/requirements/index.md` ровно одна актуальная версия.
- [ ] Предыдущая версия помечена «Замещена», файл не изменён.
- [ ] Changelog соответствует фактическим изменениям.
- [ ] README и `.session-context.md` ссылаются на актуальную версию.
- [ ] System Design обновлён до той же версии, что и ТЗ.

## Как искать

Используй `grep`/`glob` по `docs/` и `README.md`. Не считай находки в исторических версиях
ТЗ (статус «Замещена») и в changelog `docs/requirements/index.md`: там старые термины
упоминаются намеренно.

Что искать:

- `required_by_default` — не должно быть нигде, кроме истории.
- `Field`/`Enum` без суффикса `Def` — только в исторических версиях и changelog.
- `--format` — только как часть `--output-format`; отдельного флага быть не должно.
- `MGxxx` — каждый код должен иметь один смысл; диапазоны — см. примечание в чек-листе.
- `v1.x` — сверь статусы в `docs/requirements/index.md` с README и System Design.

## Формат отчёта

- **Critical** — противоречие контракту или поведению.
- **Major** — устаревший/неполный раздел.
- **Minor** — терминология, ссылки, стиль.

Для каждой находки: `file:line`, цитата, проблема, предлагаемое исправление.
В конце — список проверенных разделов и явное заключение о согласованности.
