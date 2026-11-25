# Релиз

## Ветвление

Проект использует trunk-based development: постоянная ветка одна — `main`
(см. [ADR-0015](adr/0015-branching-and-release-policy.md)).

- работа — в `feat/*`, `fix/*`, `docs/*`, `chore/*`;
- merge в `main` — только через PR и зелёный `ci-success`;
- релиз — тег `vX.Y.Z` на `main`;
- для старой линии или стабилизации — временная `release/X.Y`;
- постоянная `develop` не используется.

## Подготовка

До 1.0 проект находится в beta-статусе: тег `v0.x` не гарантирует обратную совместимость
(см. [ADR-0014](adr/0014-beta-status-and-compatibility.md)).

1. Запустить `uv run python tools/bump_version.py <version>`:
   обновляет `pyproject.toml` и `src/eggpipe/version.py`, выполняет `uv lock`,
   переносит `[Unreleased]` в `[<version>] - <date>` и пересобирает `docs/ai`.
2. Проверить diff. Версия `mike` вычисляется из `pyproject.toml` в workflow `pages`.
3. Проверить `uv lock --check`.
4. Прогнать локально:

   ```bash
   uv run python tools/check_docs.py --strict
   uv run ruff check .
   uv run ruff format --check src tests tools examples
   uv run pyrefly check
   uv run pytest --cov
   uv build
   uv run python tools/check_wheel.py dist
   uv run mkdocs build --strict
   ```

5. Проверить, что все deprecated-элементы либо остаются в окне поддержки, либо удалены
   по [ADR-0016](adr/0016-deprecation-policy.md).
6. Убедиться, что `LICENSE`, `README.md` и `CHANGELOG.md` попадают в sdist.
7. Проверить доступность имени `eggpipe` и команды `eggpipe` на PyPI.

## Версия в документации

Текущая версия пакета хранится в одном месте — `pyproject.toml` (зеркало в
`src/eggpipe/version.py`). Живые документы её не дублируют: используют плейсхолдер `X.Y.Z`,
ссылку на `pyproject.toml`/`CHANGELOG.md` или генерируемые значения
(`docs/ai/manifest.json`).

Конкретные версии допустимы в записях и данных: CHANGELOG, session-log, ADR, ревью,
требования (включая актуальное ТЗ), roadmap (метки вех), backlog, PR-шаблон, примеры.

`tools/check_docs.py` проверяет это проверкой `DOC161`: литерал текущей версии вне allowlist —
ошибка CI. Проверка эвристическая: внешний пакет, запиненный на ту же версию в прозе вне
код-фенса, тоже будет отмечен. Свежесть `docs/ai` проверяется отдельно (B-025).
Нормативная база — [ADR-0022](adr/0022-documentation-version-policy.md).

## Публикация

Тег ставится только на `main` после merge release PR. Прямой push в `main` запрещён.
Теги `v*` защищены; опубликованные теги не перемещаются и не удаляются.

Релиз запускается тегом:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Workflow `.github/workflows/release.yml`:

- `build` — проверки, сборка, `check_wheel.py` и SBOM `sbom/sbom.cdx.json`;
- `github-release` — GitHub Release с wheel/sdist и SBOM;
- `publish-pypi` — PyPI через trusted publisher, только если repository variable
  `PYPI_PUBLISH=true`. Attestations PEP 740 включены по умолчанию в используемой версии
  `pypa/gh-action-pypi-publish@release/v1`.

Для PyPI настроить trusted publisher:

1. Убедиться, что имя `eggpipe` доступно на PyPI.
2. PyPI → **Publishing** → **Add a new pending publisher**:
   - PyPI project name: `eggpipe`;
   - owner: GitHub-владелец репозитория;
   - repository: имя репозитория;
   - workflow name: `release.yml`;
   - environment: `pypi`.
3. GitHub → **Settings → Environments** → создать environment `pypi`.
   Секреты не нужны: используется OIDC (`id-token: write`). Рекомендуется включить
   required reviewers, чтобы публикация не проходила без подтверждения.
4. GitHub → **Settings → Secrets and variables → Actions → Variables**:
   добавить `PYPI_PUBLISH=true`.
5. Запушить тег:

   ```bash
   git push origin vX.Y.Z
   ```

Без `PYPI_PUBLISH=true` артефакты публикуются только в GitHub Release.
Эти шаги нельзя выполнить из репозитория: нужны доступы к PyPI и настройкам GitHub.

## Документация

Версия документации — `major.minor` (например, `1.2` для пакета `1.2.0`), alias `latest` указывает на
последнюю версию. Workflow `pages` собирает версии через `mike` и публикует artifact
на GitHub Pages; старые версии сохраняются по путям `/1.1/`, `/1.2/` и т.д.

## После релиза

- Проверить установку из PyPI: `pip install eggpipe`.
- Проверить версию документации: https://spigit.github.io/eggpipe/latest/.
- Проверить публикацию документации: https://spigit.github.io/eggpipe/.
- Проверить `eggpipe --help`, `eggpipe model schema`, `eggpipe format list`.
- Добавить `[Unreleased]` в CHANGELOG для следующей версии.
