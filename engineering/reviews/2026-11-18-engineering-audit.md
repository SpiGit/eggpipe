# Аудит инженерной документации — 2026-11-18

- **Статус:** выполнен; P0/P1 исправлены, P2 зафиксированы для следующего касания.
- **База:** `main` после #38, ТЗ v2.4, ADR-0018.
- **Метод:** сверка ТЗ, ADR, System Design, roadmap, session-log, backlog, harness,
  `docs/user`, `docs/ai`, CHANGELOG и release-документов; `check_docs --strict`.

## 1. P0 — исправлено

| Находка | Исправление |
|---------|-------------|
| §6.1.1 ТЗ говорил `EG301` для неизвестной аннотации, а §9.1/код/доки — `EG302` | `v2.4.md` §6.1.1: `EG302` |
| System Design описывал `EG001` как ошибку enum/type, хотя ТЗ резервирует код | System Design §4.4: `EG001` зарезервирован |

## 2. P1 — исправлено

- Roadmap: фактический scope 0.4.0, шаблон/contract-тесты отмечены готовыми, убран stale hash.
- Roadmap: статусы сведены к §4, §1.1 и §8 больше не дублируют их.
- ТЗ v2.4: матрица версий обновлена до 2.4 / 0.3.2; ADR-практика — 0001–0018.
- System Design: `Engine.build/generate/check(entities=...)`, exit code `EG303`,
  правила per-entity manifest (`generated_at`, `input_fingerprint`), формат тестов.
- CONTRIBUTING и `docs/ai/invariants`: исторические ТЗ — все версии со статусом «Замещена».
- `plan-v2.md` помечен историческим; `engineering/index.md` ведёт к roadmap.
- `/spec-release` обновляет `engineering/requirements/changelog.md`, а не `index.md`.
- Skill `spec-consistency` знает `--entity`, `output_scope`, `EG303`, per-entity manifest.
- session-log: per-entity реализована, CI-матрица 3.11–3.15.
- README: добавлены ADR-0011–0018 и ревью 2026-11-13.
- `docs/user/cli.md`: `gen list --all`, `--clean` + EG030, `--no-color`.
- `AGENTS.md`, `README.md`, `.session-context.md`: `Engine.build/generate/check(entities=...)`.

## 3. P2 — зафиксировано

- В ТЗ остались исторические формулировки «в v2.1»; при следующей версии заменить на
  «в текущей версии».
- ADR-0003–0006, 0011–0012 содержат `MGxxx`/`GeneratorRules*`; в `adr/index.md` добавлена
  общая пометка о чтении как `EGxxx`/`ProjectConfig*`. Переписывать ADR не нужно.
- `docs/user` использует «модель» для YAML-документа; терминология будет уточнена при
  следующем касании concepts/index.
- `docs/ai` не проверяется на свежесть в preflight; `build_ai_docs.py` пока только пишет.
- `tools/preflight.py` не проверяет `docs/ai`; добавить `--check`-режим при следующем
  изменении harness.
- `docs/user/api/format.md`: формулировка «нельзя выходить за project root» для
  `input_paths` шире ТЗ; уточнить при следующем касании format API.

P2 не заводятся в backlog отдельными строками: они относятся к документации и закрываются
пакетно при следующем docs-изменении или перед релизом 0.4.0.

## 4. Следующий аудит

- Перед тегом `0.4.0`.
- После Plugin DX: проверить, что roadmap, 0.4.0 checklist, release.md и CHANGELOG совпадают.
- После релиза: обновить current point и удалить выполненные пункты из 0.4.0.
