"""CLI metadata-generator (v0.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from metadata_generator.config.app_config import AppConfig
from metadata_generator.config.generator_rules import GeneratorRules, GeneratorRulesLoader
from metadata_generator.core.parser import Parser
from metadata_generator.core.validator import validate_document
from metadata_generator.engine.artifact_writer import ArtifactWriter
from metadata_generator.engine.engine import Engine
from metadata_generator.engine.plugin_loader import (
    GENERATOR_GROUP,
    build_format_registry,
    load_generators,
    load_local_generators,
)
from metadata_generator.engine.report import EngineReport
from metadata_generator.interfaces.generator import GeneratorPlugin
from metadata_generator.utils.exceptions import (
    ConfigValidationError,
    DocumentError,
    MetadataGeneratorError,
)
from metadata_generator.version import __version__
from metadata_generator.watch.watcher import run_watch

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Metadata Generator")
config_app = typer.Typer(no_args_is_help=True, help="Конфигурация")
model_app = typer.Typer(no_args_is_help=True, help="Модели")
gen_app = typer.Typer(no_args_is_help=True, help="Генераторы")
format_app = typer.Typer(no_args_is_help=True, help="Форматы")
app.add_typer(config_app, name="config")
app.add_typer(model_app, name="model")
app.add_typer(gen_app, name="gen")
app.add_typer(format_app, name="format")

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Путь к .mg.yaml"),
]
GeneratorOption = Annotated[
    list[str] | None,
    typer.Option("--generator", "-g", help="Генераторы: через запятую или повторно"),
]


def _load_rules(config_path: Path | None) -> tuple[GeneratorRules, Path]:
    path = config_path or GeneratorRulesLoader.discover()
    if path is None:
        raise ConfigValidationError("не найден .mg.yaml; укажите --config")
    rules = GeneratorRulesLoader().load(path)
    return rules, path.resolve().parent


def _selected_generators(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    result: set[str] = set()
    for value in values:
        result.update(item.strip() for item in value.split(",") if item.strip())
    return result or None


def _filter_rules(rules: GeneratorRules, selected: set[str] | None) -> GeneratorRules:
    if selected is None:
        return rules
    known = {item.id for item in rules.generators}
    unknown = selected - known
    if unknown:
        raise ConfigValidationError(f"неизвестные генераторы: {', '.join(sorted(unknown))}")
    return rules.model_copy(
        update={"generators": tuple(item for item in rules.generators if item.id in selected)}
    )


def _parse_variables(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values or []:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise ConfigValidationError(f"некорректный --var: {item!r}")
        result[key] = value
    return result


def _load_generators(plugins: list[Path] | None) -> dict[str, GeneratorPlugin]:
    generators = dict(load_generators())
    if plugins:
        generators.update(load_local_generators(plugins))
    return generators


def _print_report(
    report: EngineReport,
    *,
    output_format: str,
    quiet: bool,
    verbose: bool,
    strict: bool,
    ignore: str | None,
) -> int:
    ignored = {item.strip() for item in (ignore or "").split(",") if item.strip()}
    diagnostics = [item for item in report.diagnostics if item.code not in ignored]
    warnings = [item for item in diagnostics if item.level == "warning"]
    errors = [item for item in diagnostics if item.level == "error"]
    success = (
        not errors
        and all(generator.status != "error" for generator in report.generators)
        and not (strict and warnings)
    )
    exit_code = 0 if success else 1
    report = report.model_copy(
        update={"diagnostics": diagnostics, "success": success, "exit_code": exit_code}
    )

    if output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return exit_code

    for item in diagnostics:
        if item.level == "error" or verbose or not quiet:
            location = _location(item.location)
            typer.echo(f"{item.level}: {item.code}: {item.message}{location}", err=True)
    if not quiet:
        for generator in report.generators:
            typer.echo(f"[{generator.status}] {generator.id} ({generator.duration_ms} ms)")
        if verbose:
            for artifact in report.artifacts:
                typer.echo(f"  {artifact.status}: {artifact.path}")
        typer.echo("OK" if success else "FAILED")
    return exit_code


def _location(location: Any) -> str:
    if location is None:
        return ""
    parts = [str(value) for value in (location.file, location.entity, location.field) if value]
    return f" ({':'.join(parts)})" if parts else ""


def _run_engine(
    *,
    models: list[Path] | None,
    config: Path | None,
    generator: list[str] | None,
    plugins: list[Path] | None,
    output: Path | None,
    variables: list[str] | None,
    plan: bool,
    check: bool,
    force: bool,
    strict: bool,
    include_disabled: bool,
    allow_outside_imports: bool,
    clean: bool,
    output_format: str,
    ignore: str | None,
    quiet: bool,
    verbose: bool,
) -> None:
    if output_format not in {"text", "json"}:
        raise ConfigValidationError("--output-format должен быть text или json")
    rules, config_dir = _load_rules(config)
    rules = _filter_rules(rules, _selected_generators(generator))
    app_config = AppConfig(
        rules_file=config,
        output_root=output,
        force=force,
        include_disabled=include_disabled,
        allow_outside_imports=allow_outside_imports,
        clean=clean,
        quiet=quiet,
        verbose=verbose,
    )
    engine = Engine(
        app_config,
        rules,
        config_dir=config_dir,
        source_paths=models,
        variables=_parse_variables(variables),
        generators=_load_generators(plugins),
    )
    if check:
        report = engine.check()
    elif plan:
        report = engine.build()
    else:
        report = engine.generate()
    code = _print_report(
        report,
        output_format=output_format,
        quiet=quiet,
        verbose=verbose,
        strict=strict,
        ignore=ignore,
    )
    raise typer.Exit(code=code)


@app.command()
def generate(
    models: Annotated[
        list[Path] | None, typer.Argument(help="Модели (по умолчанию sources)")
    ] = None,
    config: ConfigOption = None,
    generator: GeneratorOption = None,
    plugin: Annotated[list[Path] | None, typer.Option("--plugin")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    variable: Annotated[list[str] | None, typer.Option("--var")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    plan: Annotated[bool, typer.Option("--plan")] = False,
    check: Annotated[bool, typer.Option("--check")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
    strict: Annotated[bool, typer.Option("--strict")] = False,
    include_disabled: Annotated[bool, typer.Option("--include-disabled")] = False,
    allow_outside_imports: Annotated[bool, typer.Option("--allow-outside-imports")] = False,
    clean: Annotated[bool, typer.Option("--clean")] = False,
    output_format: Annotated[str, typer.Option("--output-format")] = "text",
    ignore: Annotated[str | None, typer.Option("--ignore")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    no_color: Annotated[bool, typer.Option("--no-color")] = False,
) -> None:
    """Сгенерировать артефакты."""
    del no_color
    try:
        _run_engine(
            models=models,
            config=config,
            generator=generator,
            plugins=plugin,
            output=output,
            variables=variable,
            plan=plan or dry_run,
            check=check,
            force=force,
            strict=strict,
            include_disabled=include_disabled,
            allow_outside_imports=allow_outside_imports,
            clean=clean,
            output_format=output_format,
            ignore=ignore,
            quiet=quiet,
            verbose=verbose,
        )
    except (ConfigValidationError, DocumentError, MetadataGeneratorError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command()
def init(
    path: Annotated[Path, typer.Argument()] = Path(".mg.yaml"),
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Создать минимальный .mg.yaml."""
    if path.exists() and not force:
        typer.echo(f"error: {path} уже существует; используйте --force", err=True)
        raise typer.Exit(code=2)
    path.write_text(
        'version: "1.0"\nsources:\n  - path: ./model.yaml\ngenerators: []\n',
        encoding="utf-8",
    )
    typer.echo(f"created {path}")


@app.command()
def watch(
    models: Annotated[
        list[Path] | None, typer.Argument(help="Модели (по умолчанию sources)")
    ] = None,
    config: ConfigOption = None,
    generator: GeneratorOption = None,
    plugin: Annotated[list[Path] | None, typer.Option("--plugin")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    variable: Annotated[list[str] | None, typer.Option("--var")] = None,
    strict: Annotated[bool, typer.Option("--strict")] = False,
    include_disabled: Annotated[bool, typer.Option("--include-disabled")] = False,
    allow_outside_imports: Annotated[bool, typer.Option("--allow-outside-imports")] = False,
    output_format: Annotated[str, typer.Option("--output-format")] = "text",
    ignore: Annotated[str | None, typer.Option("--ignore")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    debounce: Annotated[int, typer.Option("--debounce")] = 300,
) -> None:
    """Watch-режим: перегенерация при изменении sources."""
    try:
        path = config or GeneratorRulesLoader.discover()
        if path is None:
            raise ConfigValidationError("не найден .mg.yaml; укажите --config")
        path = path.resolve()
        rules, config_dir = _load_rules(path)
        rules = _filter_rules(rules, _selected_generators(generator))
        generators = _load_generators(plugin)
        output_root = (output or config_dir).resolve()
        source_paths = [
            item if item.is_absolute() else (config_dir / item).resolve()
            for item in (models or [source.path for source in rules.sources])
        ]
        ignored_dirs = {(output_root / item.output_dir).resolve() for item in rules.generators}

        def run_once() -> int:
            current_rules, current_dir = _load_rules(path)
            current_rules = _filter_rules(current_rules, _selected_generators(generator))
            app_config = AppConfig(
                rules_file=path,
                output_root=output,
                force=False,
                include_disabled=include_disabled,
                allow_outside_imports=allow_outside_imports,
                quiet=quiet,
                verbose=verbose,
            )
            engine = Engine(
                app_config,
                current_rules,
                config_dir=current_dir,
                source_paths=models,
                variables=_parse_variables(variable),
                generators=generators,
            )
            report = engine.generate()
            return _print_report(
                report,
                output_format=output_format,
                quiet=quiet,
                verbose=verbose,
                strict=strict,
                ignore=ignore,
            )

        run_watch(
            config_path=path,
            source_paths=source_paths,
            ignored_dirs=ignored_dirs,
            debounce_ms=debounce,
            run_once=run_once,
        )
    except (ConfigValidationError, DocumentError, MetadataGeneratorError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@config_app.command("show")
def config_show(
    config: ConfigOption = None,
    show_secrets: Annotated[bool, typer.Option("--show-secrets")] = False,
) -> None:
    """Показать merged config."""
    try:
        rules, _ = _load_rules(config)
    except MetadataGeneratorError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    data = rules.model_dump(mode="json")
    if not show_secrets:
        data["variables"] = _redact(data.get("variables", {}))
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


@config_app.command("validate")
def config_validate(config: ConfigOption = None) -> None:
    """Проверить .mg.yaml."""
    try:
        _load_rules(config)
    except MetadataGeneratorError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo("OK")


def _redact(values: dict[str, str]) -> dict[str, str]:
    secret_markers = ("token", "secret", "password")
    return {
        key: "***" if any(marker in key.lower() for marker in secret_markers) else value
        for key, value in values.items()
    }


@model_app.command("validate")
def model_validate(
    models: Annotated[list[Path], typer.Argument()],
    output_format: Annotated[str, typer.Option("--output-format")] = "text",
) -> None:
    """Проверить модели."""
    parser = Parser()
    diagnostics = []
    for path in models:
        try:
            diagnostics.extend(validate_document(parser.parse_document(path)))
        except DocumentError as exc:
            typer.echo(f"error: {exc.code}: {exc.message} ({exc.path})", err=True)
            raise typer.Exit(code=2) from exc
    if output_format == "json":
        typer.echo(
            json.dumps(
                [item.model_dump(mode="json") for item in diagnostics],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for item in diagnostics:
            typer.echo(f"{item.level}: {item.code}: {item.message}", err=True)
        typer.echo("OK" if not any(item.level == "error" for item in diagnostics) else "FAILED")
    raise typer.Exit(code=0 if not any(item.level == "error" for item in diagnostics) else 1)


@gen_app.command("list")
def gen_list(
    show_all: Annotated[bool, typer.Option("--all")] = False,
) -> None:
    """Список генераторов из entry points."""
    del show_all
    plugins = load_generators()
    if not plugins:
        typer.echo("no generators")
        return
    for generator_id, plugin in sorted(plugins.items()):
        typer.echo(f"{generator_id}\t{plugin.name or generator_id}\tapi={plugin.api_version}")


@gen_app.command("info")
def gen_info(generator_id: str) -> None:
    """Информация о генераторе."""
    plugin = load_generators().get(generator_id)
    if plugin is None:
        typer.echo(f"error: неизвестный генератор: {generator_id}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"id: {plugin.id}")
    typer.echo(f"name: {plugin.name or plugin.id}")
    typer.echo(f"api_version: {plugin.api_version}")
    typer.echo(f"entry point group: {GENERATOR_GROUP}")


@format_app.command("list")
def format_list() -> None:
    """Список форматов."""
    for item in build_format_registry().list():
        typer.echo(f"{item.name}\tversions={','.join(item.versions)}")


@app.command()
def clean(
    config: ConfigOption = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    yes: Annotated[bool, typer.Option("--yes")] = False,
) -> None:
    """Удалить unchanged owned-артефакты из manifest."""
    del yes
    try:
        rules, config_dir = _load_rules(config)
    except MetadataGeneratorError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    writer = ArtifactWriter(mg_version=__version__)
    base = (output or config_dir).resolve()
    removed = 0
    for generator in rules.generators:
        output_dir = (base / generator.output_dir).resolve()
        diagnostics = writer.clean_manifest(
            output_dir=output_dir,
            generator_id=generator.id,
            dry_run=dry_run,
        )
        for item in diagnostics:
            typer.echo(f"{item.level}: {item.code}: {item.message}", err=True)
        removed += 1
    typer.echo(f"{'planned' if dry_run else 'cleaned'} manifests: {removed}")


if __name__ == "__main__":
    app()
