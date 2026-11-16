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
