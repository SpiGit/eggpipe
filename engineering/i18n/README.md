# Russian translation memory

Baseline перед переходом к English-only: commit `9924fa5`.

Файлы:

- `ru-messages.yaml` — все русские строковые константы из `src/`, `tests/`, `tools/`, `examples/`.
- `ru-docstrings.yaml` — все русские docstrings.

Это не runtime-каталог и не часть публичного API. Цель — сохранить исходные русские
формулировки до перевода кода на английский.

Комментарии в код не входят: они восстанавливаются из Git-истории:

```bash
git show 9924fa5:src/eggpipe/core/layers.py
```

Если позже понадобится i18n, из `ru-messages.yaml` можно собрать gettext-каталог `ru`.
