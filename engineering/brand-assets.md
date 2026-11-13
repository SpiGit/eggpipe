# Brand assets

Иконка и изображения Eggpipe. Исходная концепция — [logo-brief](decisions/logo-brief.md).

## Структура

```text
docs/assets/brand/
├── svg/                         # векторные мастера
├── png/                         # экспорты для документации и приложений
├── lockup/                      # wordmark и lockup, SVG + PNG light/dark
├── social/                      # GitHub social preview
├── favicon.ico
├── preview.png
└── preview-small-sizes.png
```

## Preview

![Icon variants](../docs/assets/brand/preview.png)

![Small sizes](../docs/assets/brand/preview-small-sizes.png)

<img src="../docs/assets/brand/lockup/eggpipe-wordmark-light.png" alt="Eggpipe wordmark" width="420">

<img src="../docs/assets/brand/lockup/eggpipe-lockup-light.png" alt="Eggpipe lockup" width="420">

## Где используется

| Место | Файл |
|-------|------|
| MkDocs, логотип в сайдбаре | `docs/assets/brand/png/eggpipe-icon-128.png` |
| MkDocs, favicon | `docs/assets/brand/favicon.ico` → копия в `docs/img/favicon.ico` |
| README, светлая тема | `docs/assets/brand/lockup/eggpipe-wordmark-light.png` |
| README, тёмная тема | `docs/assets/brand/lockup/eggpipe-wordmark-dark.png` |
| `docs/index.md` | `docs/assets/brand/lockup/eggpipe-wordmark-light.png` и dark-вариант |
| Lockup с иконкой | `docs/assets/brand/lockup/eggpipe-lockup-light.png`, `docs/assets/brand/lockup/eggpipe-lockup-dark.png` |
| GitHub social preview | `docs/assets/brand/social/eggpipe-social-1280x640.png` |
| GitHub avatar | `docs/assets/brand/png/eggpipe-icon-512.png` |
| PyPI README | те же PNG по абсолютным URL после появления репозитория |
| Android / PWA | `docs/assets/brand/png/android-chrome-192x192.png`, `docs/assets/brand/png/android-chrome-512x512.png` |
| Apple touch icon | `docs/assets/brand/png/apple-touch-icon.png` |

## Размеры

| Размер | Версия |
|--------|--------|
| 16px | упрощённый `P` |
| 32–64px | упрощённый `EP` без яйца и фланцев |
| 128px+ | детальный знак с яйцом, `EP` и трубой |

Квадратные версии сохраняют исходные пропорции: знак не сжимается по вертикали,
свободное место добавляется по бокам.

## Варианты

- `eggpipe-icon.svg` — мастер 511:665;
- `eggpipe-icon-original.svg` — 787:1024;
- `eggpipe-icon-square.svg` — квадрат 1024;
- `eggpipe-icon-dark.svg` — eggshell вместо slate, teal `#3FA9BD`;
- `eggpipe-icon-mono.svg` — один цвет slate;
- `eggpipe-icon-mono-light.svg` — один цвет eggshell.

## Lockup

Векторные мастера:

- `lockup/eggpipe-wordmark.svg` — wordmark;
- `lockup/eggpipe-wordmark-dark.svg` — wordmark для тёмного фона;
- `lockup/eggpipe-lockup.svg` — иконка + wordmark;
- `lockup/eggpipe-lockup-dark.svg` — lockup для тёмного фона.

PNG-экспорты:

- `lockup/eggpipe-wordmark-light.png`, `lockup/eggpipe-wordmark-dark.png`;
- `lockup/eggpipe-lockup-light.png`, `lockup/eggpipe-lockup-dark.png`.

PNG для README и docs собраны из исходного растрового wordmark: так сохраняется
тоньше штрих. SVG-версии — черновой автотрейс, они тяжелее и пока не используются
для экспорта.

## Ограничения

- SVG иконки и wordmark получены автотрассировкой исходных PNG. Wordmark SVG
  тяжелее оригинала; PNG-экспорты собраны из растрового источника.
  Перед публичным релизом кривые желательно перерисовать вручную в Figma/Inkscape.
- `social/eggpipe-social-1280x640.png` собран из векторного lockup; tagline в нём
  пока растровый.
- `apple-touch-icon.png` — единственный PNG с фоном, так требует iOS.

## Пересборка

Исходный скрипт сборки и промежуточные файлы лежат в `.local/logo-build/` (не коммитится).
После изменения SVG можно пересобрать PNG тем же скриптом и скопировать результат сюда.
