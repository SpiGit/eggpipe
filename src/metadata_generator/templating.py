"""Опциональный helper для Jinja2-шаблонов плагинов.

Ядро не использует шаблонизатор и не импортирует Jinja2 при старте. Модуль доступен
только при установленном extra ``[jinja]``; плагин вызывает его явно, чтобы не
дублировать загрузку ``PackageLoader``/``FileSystemLoader``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from metadata_generator.utils.exceptions import MetadataGeneratorError

if TYPE_CHECKING:
    from jinja2 import Environment


class TemplateError(MetadataGeneratorError):
    """Ошибка загрузки или рендеринга шаблона."""


def jinja_environment(
    *,
    package: str | None = None,
    templates_dir: str | Path | None = None,
    config_dir: Path | None = None,
    **environment_options: Any,
) -> Environment:
    """Создать Jinja2-окружение для шаблонов плагина.

    Args:
        package: Пакет с каталогом ``templates`` внутри (``PackageLoader``).
        templates_dir: Каталог шаблонов пользователя; имеет приоритет над ``package``.
        config_dir: База для относительного ``templates_dir``.
        **environment_options: Дополнительные аргументы ``jinja2.Environment``.

    Raises:
        TemplateError: Jinja2 не установлен, каталог не найден или шаблоны пакета
            недоступны.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined
    except ImportError as exc:
        raise TemplateError("jinja2 не установлен; установите metadata-generator[jinja]") from exc

    if templates_dir is not None:
        path = Path(templates_dir)
        if not path.is_absolute() and config_dir is not None:
            path = config_dir / path
        if not path.is_dir():
            raise TemplateError(f"каталог шаблонов не найден: {path}")
        loader = FileSystemLoader(str(path))
    elif package is not None:
        try:
            loader = PackageLoader(package, "templates")
        except (ImportError, ValueError) as exc:
            raise TemplateError(f"не удалось загрузить шаблоны пакета {package}: {exc}") from exc
    else:
        raise TemplateError("укажите package или templates_dir")

    options: dict[str, Any] = {
        "autoescape": False,
        "keep_trailing_newline": True,
        "trim_blocks": True,
        "lstrip_blocks": True,
        "undefined": StrictUndefined,
    }
    options.update(environment_options)
    return Environment(loader=loader, **options)


def render_template(environment: Environment, template_name: str, /, **context: Any) -> str:
    """Загрузить и отрендерить шаблон, преобразуя ошибки Jinja2 в TemplateError."""
    from jinja2 import TemplateError as JinjaTemplateError

    try:
        template = environment.get_template(template_name)
        return template.render(**context)
    except JinjaTemplateError as exc:
        raise TemplateError(f"ошибка шаблона {template_name}: {exc}") from exc


__all__ = ["TemplateError", "jinja_environment", "render_template"]
