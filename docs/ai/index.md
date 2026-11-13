# AI documentation

Раздел для AI-агентов, работающих с Eggpipe.

- [Context](context.md) — идентичность, публичный API, команды и инварианты.
- [Tasks](tasks.md) — типовые задачи: генератор, формат, диагностика, изменение поведения.
- [Invariants](invariants.md) — жёсткие правила.
- [llms.txt](llms.txt) — краткий индекс для LLM (plain text).
- [llms-full.txt](llms-full.txt) — полный контекст одним файлом.
- [manifest.json](manifest.json) — карта документов, API и команд.
- [diagnostics.json](diagnostics.json) — машиночитаемый каталог EGxxx.
- [schemas/](schemas/model.schema.json) — JSON Schema модели, конфига, отчёта и manifest.

Пересборка:

```bash
uv run python tools/build_ai_docs.py
```
