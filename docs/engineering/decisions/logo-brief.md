# Бренд: требования к логотипу

- **Статус:** черновик, концепция выбрана
- **Дата:** 2026-11-13
- **Связанные документы:** [Решения о проекте](./eggpipe.md), [ТЗ v2.2](../requirements/v2.2.md)

---

## 1. Контекст

Название **Eggpipe** соединяет две идеи: яйцо (модель, начало) и трубу/pipeline
(генераторы, поток данных). Логотип должен читаться как технический инструмент,
но без тяжёлой индустриальности.

Исходный холст содержал четыре концепта. Нумерация: слева направо, сверху вниз.

| № | Концепт | Решение |
|---|---------|---------|
| 1 | Монограмма `EP` в контуре яйца, `P` в виде трубы | **Иконка** после упрощения |
| 2 | Яйцо в кольце трубы с фланцами | Не используем |
| 3 | Вылупление: яйцо, трещины, код, шестерёнка, документ | Иллюстрация, не логотип |
| 4 | Wordmark `EggPipe`, `P` с яйцом и трубой | **Wordmark** |

Выбранная система:

```text
icon (1) + wordmark (4) = lockup
```

- **Иконка** — квадратный знак для favicon, аватара, README и docs.
- **Wordmark** — основная надпись `EggPipe`.
- **Lockup** — иконка слева, wordmark справа.
- **Иллюстрация (3)** — опционально для tutorial/README, не часть логотипа.

Концепт 2 не используем.

## 2. Что подходит из текущих файлов

Текущий PNG — эскиз для ревью, а не финальный ассет.

- Концепт 1 — основа иконки; требует упрощения.
- Концепт 4 — основа wordmark; слоган нужно вынести отдельно.
- Концепт 3 — можно использовать как иллюстрацию.
- Концепт 2 — исключён.

Раздельные PNG для ревью лежат в `.local/logo-concepts/` (каталог игнорируется git):

```text
.local/logo-concepts/
├── concept-1.png
├── concept-2.png
├── concept-3.png
└── concept-4.png
```

## 3. Доработка концепта 1 (иконка)

Проблемы текущего эскиза:

- контур яйца и фланцы трубы слишком тонкие для 16×16;
- `E` и `P` отличаются по толщине и характеру штриха;
- разрыв контура яйца сверху и снизу читается как случайная ошибка;
- мелкие фланцы теряются при уменьшении.

Требования:

1. Утолщить контур яйца до толщины `P` или убрать его в small-версии.
2. Оставить у `P` максимум два фланца; для 16px — убрать фланцы.
3. Выровнять `E` и `P` по высоте и толщине штриха.
4. Сделать контур яйца замкнутым либо осознанно разомкнутым, но не «случайным».
5. Подготовить монохромную версию — весь знак одним цветом.
6. Подготовить small-версию: только `EP`, без яйца, с толстыми штрихами.

## 4. Доработка концепта 4 (wordmark)

Требования:

1. Убрать слоган `one model → many artifacts` из основного wordmark.
2. Сделать отдельный вариант со слоганом.
3. В монохроме яйцо внутри `P` — прозрачное или белое, не жёлтое.
4. Упростить фланец на ножке `P` для маленьких размеров.
5. В wordmark использовать `EggPipe`; пакет и CLI остаются `eggpipe`.
6. Подобрать геометрический шрифт: Inter, Manrope, IBM Plex Sans или Space Grotesk.
   `P` рисуется вручную.
7. Подготовить варианты: без слогана, со слоганом, монохром, для тёмного фона.

## 5. Палитра

| Роль | Цвет |
|------|------|
| Eggshell | `#F7F3E8` |
| Yolk | `#F2B705` |
| Pipeline teal | `#1F7A8C` |
| Slate | `#1F2937` |
| Accent coral | `#E4572E` |

## 6. Обязательные файлы

### Векторные мастера

| Файл | Формат | Назначение |
|------|--------|------------|
| `eggpipe-icon.svg` | SVG | Основная иконка |
| `eggpipe-icon-small.svg` | SVG | Упрощённая версия для 16–24px |
| `eggpipe-icon-mono.svg` | SVG | Монохром |
| `eggpipe-wordmark.svg` | SVG | Название без слогана |
| `eggpipe-wordmark-mono.svg` | SVG | Монохром |
| `eggpipe-lockup.svg` | SVG | Иконка + название |
| `eggpipe-lockup-dark.svg` | SVG | Для тёмного фона |

Текст в SVG переводится в кривые. Финальный мастер — только вектор.

### PNG-экспорты

| Файл | Размер |
|------|--------|
| `eggpipe-icon-16.png` … `eggpipe-icon-1024.png` | 16, 32, 48, 64, 128, 256, 512, 1024 |
| `eggpipe-lockup-1024.png` | 1024 по ширине |
| `eggpipe-social-1280x640.png` | 1280×640 |
| `favicon.ico` | 16/32/48 в одном файле |

Требования к PNG: прозрачный фон, sRGB, без теней и градиентов в маленьких размерах.

### Опционально

- `eggpipe-illustration.svg` / PNG — концепт 3 для документации.

## 7. Критерии приёмки

- [ ] Иконка читается на 16×16 и 32×32.
- [ ] Силуэт понятен без подписи.
- [ ] Есть light, dark и mono варианты.
- [ ] Wordmark читается без слогана; слоган не является частью основного знака.
- [ ] Все SVG с прозрачным фоном и текстом в кривых.
- [ ] Есть PNG-набор и favicon.
- [ ] Логотип не использует Python-логотип и не выглядит как фото/3D.

## 8. Промпты для image-модели

Генерировать иконку и wordmark отдельно, не одним холстом.

### Иконка

```text
Minimal flat vector logo icon for a developer tool named Eggpipe.
Monogram "EP": the letter E in slate gray, the letter P formed by a pipeline
with two coupling flanges, enclosed by a thin egg-shaped outline.
Geometric sans-serif letterforms, uniform thick strokes, high contrast.
Palette: slate #1F2937, pipeline teal #1F7A8C, yolk yellow #F2B705 accent.
Centered composition with generous padding, plain warm off-white background
#F7F3E8, no text besides EP, no gradients, no shadows, no 3D, no texture,
crisp edges, readable at 16x16, professional vector logo style, 1:1.
```

Негативный промпт:

```text
3D, gradient, bevel, shadow, glow, texture, photo, realistic, complex details,
tiny elements, multiple logos, watermark, extra letters, misspelled text,
low contrast, thin strokes, busy background
```

### Wordmark

```text
Flat vector wordmark "EggPipe" for a developer tool.
Geometric sans-serif, uppercase E and P, the bowl of P shaped as an egg
with a yolk-yellow fill, the stem of P shaped as a pipe with a coupling flange.
Slate gray and pipeline teal, clean spacing, high contrast, plain white background,
no tagline, no gradients, no shadows, no 3D, crisp vector edges, horizontal lockup.
```

Image-модели плохо воспроизводят точный текст. Для финального wordmark использовать
Figma/Inkscape и шрифт Inter/Manrope; `P` рисовать вручную.

## 9. Черновые ассеты

Черновой набор собран из концепта 1 и лежит в `docs/assets/brand/`:

- `svg/` — мастер, квадратная версия без искажения пропорций, dark, mono, small-варианты;
- `png/` — экспорты 16–1024, dark/mono, Android/Apple;
- `lockup/` — wordmark и lockup light/dark; в README используется wordmark.
- `favicon.ico` — 16/32/48;
- `preview.png` и `preview-small-sizes.png` — визуальная проверка;
- `social/eggpipe-social-1280x640.png` — GitHub social preview.

Квадратные версии не сжимают знак по вертикали: исходные пропорции сохраняются,
а свободное место добавляется по бокам.

Размерная сетка:

| Размер | Версия |
|--------|--------|
| 16px | упрощённый `P` |
| 32–64px | упрощённый `EP` без яйца и фланцев |
| 128px+ | детальный знак |

SVG получен автотрассировкой исходного PNG. Перед публикацией его желательно
перерисовать вручную в Figma/Inkscape.

## 10. Следующие шаги

1. [x] Зафиксировать выбор: концепт 1 — иконка, концепт 4 — wordmark.
2. [x] Собрать черновой SVG-набор и PNG-экспорты.
3. [x] Разложить ассеты в `docs/assets/brand/`.
4. [x] Подключить логотип в `mkdocs.yml` и README; favicon — `docs/img/favicon.ico`.
5. [ ] Перерисовать SVG-кривые вручную и пересобрать social preview после векторного wordmark.
6. [ ] Проверить на GitHub (light/dark) и PyPI после публикации.
