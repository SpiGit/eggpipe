# Релиз

## Подготовка

До 1.0 проект находится в beta-статусе: тег `v0.x` не гарантирует обратную совместимость
(см. [ADR-0014](adr/0014-beta-status-and-compatibility.md)).

1. Обновить версию в `pyproject.toml` (SemVer).
2. Перенести `[Unreleased]` в `[<version>] - <date>` в `CHANGELOG.md`.
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

5. Убедиться, что `LICENSE`, `README.md` и `CHANGELOG.md` попадают в sdist.
6. Проверить доступность имени `eggpipe` и команды `eggpipe` на PyPI.

## Публикация

Тег ставится только на `main` после merge release PR. Прямой push в `main` запрещён.

Релиз запускается тегом:

```bash
git tag v0.3.1
git push origin v0.3.1
```

Workflow `.github/workflows/release.yml`:

- `build` — проверки, сборка и `check_wheel.py`;
- `github-release` — GitHub Release с wheel/sdist;
- `publish-pypi` — PyPI через trusted publisher, только если repository variable
  `PYPI_PUBLISH=true`.

Для PyPI настроить trusted publisher:

1. Убедиться, что имя `eggpipe` доступно на PyPI.
2. PyPI → **Publishing** → **Add a new pending publisher**:
   - PyPI project name: `eggpipe`;
   - owner: GitHub-владелец репозитория;
   - repository: имя репозитория;
   - workflow name: `release.yml`;
   - environment: `pypi`.
3. GitHub → **Settings → Environments** → создать environment `pypi`.
   Секреты не нужны: используется OIDC (`id-token: write`).
4. GitHub → **Settings → Secrets and variables → Actions → Variables**:
   добавить `PYPI_PUBLISH=true`.
5. Запушить тег:

   ```bash
   git push origin v0.3.1
   ```

Без `PYPI_PUBLISH=true` артефакты публикуются только в GitHub Release.
Эти шаги нельзя выполнить из репозитория: нужны доступы к PyPI и настройкам GitHub.

## После релиза

- Проверить установку из PyPI: `pip install eggpipe`.
- Проверить `eggpipe --help`, `eggpipe model schema`, `eggpipe format list`.
- Добавить `[Unreleased]` в CHANGELOG для следующей версии.
