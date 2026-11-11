# Релиз

## Подготовка

1. Обновить версию в `pyproject.toml` (SemVer).
2. Перенести `[Unreleased]` в `[<version>] - <date>` в `CHANGELOG.md`.
3. Проверить `uv lock --check`.
4. Прогнать локально:

   ```bash
   uv run python tools/check_docs.py --strict
   uv run ruff check .
   uv run ruff format --check src tests tools
   uv run pyrefly check
   uv run pytest --cov
   uv build
   uv run python tools/check_wheel.py dist
   uv run mkdocs build --strict
   ```

5. Убедиться, что `LICENSE`, `README.md` и `CHANGELOG.md` попадают в sdist.
6. Проверить доступность имени `metadata-generator` и команды `mg` на PyPI.

## Публикация

Релиз запускается тегом:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Workflow `.github/workflows/release.yml`:

- `build` — проверки, сборка и `check_wheel.py`;
- `github-release` — GitHub Release с wheel/sdist;
- `publish-pypi` — PyPI через trusted publisher, только если repository variable
  `PYPI_PUBLISH=true`.

Для PyPI настроить trusted publisher:

- owner/repository: репозиторий проекта;
- workflow: `release.yml`;
- environment: `pypi`.

Без `PYPI_PUBLISH=true` артефакты публикуются только в GitHub Release.

## После релиза

- Проверить установку из PyPI: `pip install metadata-generator`.
- Проверить `mg --help`, `mg model schema`, `mg format list`.
- Добавить `[Unreleased]` в CHANGELOG для следующей версии.
