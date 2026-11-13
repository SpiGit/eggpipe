"""Optional helper for Jinja2 templates in plugins.

The core does not use a template engine and does not import Jinja2 at startup. This
module is available only when the ``[jinja]`` extra is installed; a plugin calls it
explicitly to avoid duplicating ``PackageLoader``/``FileSystemLoader`` setup.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from eggpipe.utils.exceptions import EggpipeError

if TYPE_CHECKING:
    from jinja2 import Environment


class TemplateError(EggpipeError):
    """Template loading or rendering error."""


def jinja_environment(
    *,
    package: str | None = None,
    templates_dir: str | Path | None = None,
    config_dir: Path | None = None,
    **environment_options: Any,
) -> Environment:
    """Create a Jinja2 environment for plugin templates.

    Args:
        package: Package that contains a ``templates`` directory (``PackageLoader``).
        templates_dir: User template directory; takes precedence over ``package``.
        config_dir: Base directory for a relative ``templates_dir``.
        **environment_options: Extra ``jinja2.Environment`` arguments.

    Raises:
        TemplateError: Jinja2 is not installed, the directory is missing, or package
            templates are unavailable.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined
    except ImportError as exc:
        raise TemplateError("jinja2 is not installed; install eggpipe[jinja]") from exc

    if templates_dir is not None:
        path = Path(templates_dir)
        if not path.is_absolute() and config_dir is not None:
            path = config_dir / path
        if not path.is_dir():
            raise TemplateError(f"template directory not found: {path}")
        loader = FileSystemLoader(str(path))
    elif package is not None:
        try:
            loader = PackageLoader(package, "templates")
        except (ImportError, ValueError) as exc:
            raise TemplateError(f"failed to load templates from package {package}: {exc}") from exc
    else:
        raise TemplateError("provide package or templates_dir")

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
    """Load and render a template, converting Jinja2 errors to TemplateError."""
    from jinja2 import TemplateError as JinjaTemplateError

    try:
        template = environment.get_template(template_name)
        return template.render(**context)
    except JinjaTemplateError as exc:
        raise TemplateError(f"template error in {template_name}: {exc}") from exc


__all__ = ["TemplateError", "jinja_environment", "render_template"]
