# ADR-0009: Глобальный manifest и ownership

- **Статус:** принято
- **Дата:** 2026-11-12
- **Связанные документы:** [ТЗ v1.4 §10](../requirements/v1.4.md), [ADR-0004](./0004-ownership-manifest-cleanup.md), [System Design §8](../system-design/index.md)
- **Актуальность:** ссылки на v1.4 исторические; действующие контракты — [ТЗ v2.2](../requirements/v2.2.md).

---

## 1. Контекст

Per-generator manifest лежал рядом с выводом:

```text
output/.mg/manifests/<generator-id>.json
```

Это создаёт проблемы:

- генератор удалён из `.mg.yaml` — manifest остался, `mg clean` его не видит;
- `output_dir` изменился — старый manifest остался в старом каталоге;
- генератор переименован — старый manifest осиротел;
- ownership зависит от того, какие генераторы сейчас настроены.

До первого релиза обратная совместимость не требуется, поэтому состояние ownership можно
перестроить.

## 2. Решение

### 2.1. Один глобальный manifest

- Файл: `.mg/manifest.json` в каталоге `.mg.yaml`.
- `manifest_version: 2`; manifest v1 не поддерживается.
- Внутри — список `locations`.

```json
{
  "manifest_version": 2,
  "locations": [
    {
      "generator": "oracle-ddl",
      "output_dir": "output/oracle",
      "mg_version": "0.1.0",
      "plugin_version": "1.2.0",
      "formats": [{"name": "entity-model", "version": "1.0"}],
      "generated_at": "2026-11-11T12:34:56Z",
      "artifacts": [{"path": "user.sql", "sha256": "...", "skipped": false}]
    }
  ]
}
```

- Ключ location — `(generator, output_dir)`.
- `output_dir` — путь относительно каталога конфига.
- `formats` — форматы среза генератора.
- `artifacts` — path/sha256/skipped.

### 2.2. Ownership

- Артефакт принадлежит location, если он есть в его `artifacts`.
- `--force` перезаписывает только **unowned** файл (нет ни в одном location).
- `--force` не отбирает файл у другого generator/location: MG041.
- Чтобы забрать файл, нужно сначала `mg clean` или удалить manifest.
- Два location не могут претендовать на один путь: exact, casefold, prefix — MG042 до записи.

### 2.3. Cleanup

- `mg clean` работает только по глобальному manifest, без `.mg.yaml` и плагинов.
- Обходит все locations, включая удалённые генераторы и старые `output_dir`.
- Удаляет unchanged owned-артефакты; изменённые вручную — MG050.
- `skipped: true` не удаляется.
- Пустые locations удаляются; если locations не осталось — manifest удаляется.
- `--dry-run` показывает план; для non-tty нужен `--yes`.

### 2.4. Смена output_dir и удаление генератора

- При смене `output_dir` новый location добавляется, старый остаётся.
- При генерации выдаётся Warning MG051 «stale generated location».
- `mg clean` удаляет старый location.
- Удалённый из конфига генератор остаётся в manifest до `mg clean`.

### 2.5. Lock и atomicity

- Один глобальный lock `.mg/lock` на `generate`/`clean`.
- `--plan`/`--check` lock не берут.
- Manifest пишется атомарно после каждого успешно записанного генератора.
- Артефакты пишутся через staging внутри `output_dir` + `os.replace`.

## 3. Последствия

- Удалён `output_dir/.mg/manifests/<generator-id>.json`.
- Ownership централизован; removed generators и старые output_dir очищаются через `mg clean`.
- `--force` больше не создаёт двойное владение.
- `mg clean` не зависит от установленных плагинов.
- Manifest не «путешествует» вместе с output_dir; это осознанный компромисс.
- Новый код MG051; обновляются MG041/MG042/MG050.

## 4. Альтернативы

- Per-generator manifest + глобальный index — отклонено: два источника состояния и сложная
  атомарность.
- Ownership через sidecar-файл рядом с каждым артефактом — отклонено: засоряет output_dir.
- Автоматически удалять старый output_dir при смене — отклонено: слишком опасно без `mg clean`.
- Разрешить `--force` отбирать файл у другого location — отклонено: двойное владение и
  небезопасный cleanup.
