# Benchmarks

- Дата: 2026-11-16
- Python: 3.11.18
- Платформа: Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.44
- Итераций: 20
- Пример: `examples/tpc-h`

| Сценарий | Медиана, мс |
|----------|-------------|
| config load | 0.917 |
| parse one document | 1.867 |
| Engine.build (TPC-H) | 70.425 |

| Фаза `build()` | Медиана, мс |
|----------------|-------------|
| discovery_ms | 34.000 |
| parse_ms | 32.500 |
| validate_ms | 0.000 |
| generate_ms | 1.000 |
| write_ms | 0.000 |
| total_ms | 69.500 |

Числа зависят от машины и не являются гарантией производительности.
Запуск: `uv run python tools/benchmark.py --iterations 20`.

## L2-кэш разбора (ADR-0020)

- Дата: 2026-11-23
- Python: 3.11.18, Linux (WSL2), те же условия, что в spike `2026-11-23`
- Пример: `examples/tpc-h`, 8 документов, реальный `tpch`-генератор, новый `Engine` на прогон
- Методика: медиана 7 прогонов после прогрева; между прогонами cachehit восстанавливался

| Сценарий | До L2, мс | После L2, мс |
|----------|-----------|--------------|
| incremental, no-op | 67 | ~5 |
| incremental, изменён 1 из 8 | 123 | ~70 (диапазон 60–100 по трём замерам) |

На changed-прогоне изменённый документ разбирается до четырёх раз (discovery,
fingerprint, parse, `remember`); переиспользование raw между фазами — кандидат
на следующий шаг. Размер кэша TPC-H: 14 КБ (9 файлов). Регрессионные пороги и
автоматическое сравнение — пункт 4 текущей вехи в [roadmap](./roadmap.md).

## Регрессионные сценарии (п. 4 вехи, [roadmap](./roadmap.md))

- Дата: 2026-11-25
- Python: 3.11.18, Linux (WSL2), те же условия, что выше
- Пример: `examples/tpc-h` (8 документов), реальный `tpch`-генератор, временная копия
  примера (`tools/benchmark.py` не трогает состояние репозитория)
- Методика: медиана 20 прогонов после прогрева, два независимых прогона на версию
  (расхождение ≤ 6 %); baseline — пакет eggpipe из PyPI (версия предыдущего релиза),
  текущая колонка — ветка `main` после L2-кэша и метрик

| Сценарий | Baseline, мс | После L2, мс | Отношение |
|----------|--------------|-----------|-----------|
| `generate` без incremental | 158.7 | 147.7 | 0.93× |
| `generate --incremental`, no-op | 119.5 | 6.0 | ~20× быстрее |
| `generate --incremental`, изменён 1 из 8 | 199.9 | 76.6 | ~2.6× быстрее |

Фазы `generate()` (медиана, мс):

| Фаза | Baseline no-op | После L2 no-op | Baseline changed | После L2 changed |
|------|----------------|-------------|------------------|---------------|
| `discovery_ms` | 62 | 4 | 63 | 16 |
| `fingerprint_ms` | 58 | 1 | 60 | 11 |
| `parse_ms` | 0 | 0 | 66 | 26 |
| `generate_ms` | 0 | 0 | 15 | 17 |
| `write_ms` | 0 | 0 | 16 | 16 |

No-op — L1-хит: прогон пропускается целиком, `parse_ms = 0`, блок `cache` в отчёте
равен `null` (ADR-0021). На changed-прогоне блок `cache` заполнен:
`hits = 7`, `misses = 1` (`changed`), `entries = 8`, `bytes ≈ 12.8 КБ`.

### Пороги приёмки

Проверяются на reference-машине выше при `tools/benchmark.py --iterations 20`.

| Метрика | Порог | Обоснование |
|---------|-------|-------------|
| full, мс | ≤ 1.3 × baseline | Полный прогон не должен деградировать из-за кэша |
| no-op, мс | ≤ 20 и ≤ 15 % full | Регрессия no-op запрещена: превышение — блокер релиза |
| no-op `discovery_ms` | ≤ 10 | Discovery не должен разбирать YAML |
| changed, мс | ≤ 130 и ≤ 80 % full | Один изменённый документ разбирается один раз |
| changed, `discovery_ms + parse_ms` | ≤ 60 | Относительная метрика разбора при incremental |
| changed, `cache.misses` | 1, причина `changed` | Остальные 7 документов — попадания |

### Воспроизведение

```bash
uv pip install -e examples/tpc-h-generator   # реальный генератор для примеров
uv run python tools/benchmark.py --iterations 20
```

Baseline предыдущего релиза измеряется тем же скриптом в отдельном окружении:

```bash
uv venv /tmp/eggpipe-baseline
uv pip install --python /tmp/eggpipe-baseline/bin/python eggpipe==0.4.0 jinja2
uv pip install --python /tmp/eggpipe-baseline/bin/python --no-deps -e examples/tpc-h-generator
/tmp/eggpipe-baseline/bin/python tools/benchmark.py --iterations 20
```


