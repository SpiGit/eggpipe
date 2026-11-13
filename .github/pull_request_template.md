# Pull request

## Что изменено

<!-- Кратко: цель и суть изменений. -->

## Проверки

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check src tests tools examples`
- [ ] `uv run pyrefly check`
- [ ] `uv run pytest --cov`
- [ ] `uv run python tools/check_docs.py --strict`
- [ ] `uv build`
- [ ] `uv run python tools/check_wheel.py dist`

## Документация

- [ ] Обновлён `CHANGELOG.md`, если изменение заметно пользователю.
- [ ] Обновлены ТЗ/ADR/System Design, если менялись контракты.
- [ ] Нет случайных файлов, `dist/`, `.venv/` и сгенерированных артефактов.
