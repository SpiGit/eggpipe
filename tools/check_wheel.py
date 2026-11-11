#!/usr/bin/env python3
"""Проверка wheel/sdist и smoke-install собранного пакета.

Запуск:
    uv run python tools/check_wheel.py dist
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from email.message import Message
from email.parser import Parser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_WHEEL_FILES = {
    "metadata_generator/__init__.py",
    "metadata_generator/py.typed",
}
REQUIRED_SDIST_FILES = {
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/metadata_generator/__init__.py",
    "src/metadata_generator/py.typed",
}
REQUIRED_DEPENDENCIES = {
    "typer",
    "pydantic",
    "pydantic-settings",
    "ruamel-yaml",
    "rich",
}


class CheckError(RuntimeError):
    """Ошибка проверки артефактов."""


@dataclass(frozen=True)
class Project:
    name: str
    version: str
    requires_python: str


def load_project(root: Path) -> Project:
    path = root / "pyproject.toml"
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CheckError(f"не удалось прочитать {path}: {exc}") from exc

    project = raw.get("project")
    if not isinstance(project, dict):
        raise CheckError("в pyproject.toml нет секции [project]")

    name = project.get("name")
    version = project.get("version")
    requires_python = project.get("requires-python")
    if not all(isinstance(value, str) for value in (name, version, requires_python)):
        raise CheckError("project.name, project.version и project.requires-python обязательны")
    assert isinstance(name, str)
    assert isinstance(version, str)
    assert isinstance(requires_python, str)
    return Project(name=name, version=version, requires_python=requires_python)


def find_artifacts(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise CheckError(
            f"в {dist} ожидались один wheel и один sdist, "
            f"найдено: {len(wheels)} wheel, {len(sdists)} sdist"
        )
    return wheels[0], sdists[0]


def dependency_name(requirement: str) -> str:
    name = re.split(r"[\s<>=!~;\\[]", requirement, maxsplit=1)[0]
    return name.lower().replace("_", "-").replace(".", "-")


def relative_sdist_names(names: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for name in names:
        parts = PurePosixPath(name).parts
        if len(parts) > 1:
            result.add("/".join(parts[1:]))
    return result


def metadata_from_wheel(archive: zipfile.ZipFile, version: str) -> Message:
    metadata_name = next(
        (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
        None,
    )
    if metadata_name is None:
        raise CheckError("в wheel нет METADATA")
    try:
        text = archive.read(metadata_name).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError(f"METADATA не является UTF-8: {exc}") from exc
    message = Parser().parsestr(text, headersonly=True)
    if message.get("Version") != version:
        raise CheckError(f"версия в METADATA не совпадает: {message.get('Version')} != {version}")
    return message


def check_metadata(message: Message, project: Project) -> None:
    expected = {
        "Name": project.name,
        "Version": project.version,
        "Requires-Python": project.requires_python,
        "License-Expression": "MIT",
    }
    for field, value in expected.items():
        if message.get(field) != value:
            raise CheckError(f"{field} в METADATA: {message.get(field)!r} != {value!r}")

    requires = message.get_all("Requires-Dist") or []
    required_names = {
        dependency_name(requirement) for requirement in requires if "extra ==" not in requirement
    }
    missing = REQUIRED_DEPENDENCIES - required_names
    if missing:
        raise CheckError(f"в METADATA нет обязательных зависимостей: {sorted(missing)}")

    extras = set(message.get_all("Provides-Extra") or [])
    for extra in ("dev", "watch"):
        if extra not in extras:
            raise CheckError(f"в METADATA нет extra {extra!r}")


def check_wheel(path: Path, project: Project) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = REQUIRED_WHEEL_FILES - names
        if missing:
            raise CheckError(f"в wheel нет файлов: {sorted(missing)}")
        forbidden = sorted(name for name in names if name.startswith(("tests/", "docs/")))
        if forbidden:
            raise CheckError(f"в wheel попали dev-файлы: {forbidden}")
        message = metadata_from_wheel(archive, project.version)
        check_metadata(message, project)
        if not any(name.endswith("/licenses/LICENSE") for name in names):
            raise CheckError("в wheel нет LICENSE")
        entry_points = next(
            (name for name in names if name.endswith(".dist-info/entry_points.txt")),
            None,
        )
        if entry_points is None:
            raise CheckError("в wheel нет entry_points.txt")
        text = archive.read(entry_points).decode("utf-8")
        if "mg = metadata_generator.cli.main:app" not in text:
            raise CheckError("в wheel нет console script mg")


def check_sdist(path: Path) -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            names = relative_sdist_names(archive.getnames())
    except (OSError, tarfile.TarError) as exc:
        raise CheckError(f"не удалось прочитать sdist {path}: {exc}") from exc

    missing = REQUIRED_SDIST_FILES - names
    if missing:
        raise CheckError(f"в sdist нет файлов: {sorted(missing)}")
    forbidden = sorted(name for name in names if name.startswith((".github/", ".opencode/")))
    if forbidden:
        raise CheckError(f"в sdist попали dev-файлы: {forbidden}")


def run_checked(command: list[str], what: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise CheckError(f"{what}: {details}")


def smoke_install(wheel: Path, version: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        environment = Path(directory) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run_checked(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--quiet",
                str(wheel.resolve()),
            ],
            "не удалось установить wheel",
        )
        run_checked(
            [
                str(python),
                "-c",
                f"import metadata_generator; assert metadata_generator.__version__ == {version!r}",
            ],
            "wheel не импортируется или версия не совпадает",
        )
        script = environment / ("Scripts/mg.exe" if sys.platform == "win32" else "bin/mg")
        run_checked([str(script), "--help"], "console script mg не работает")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка артефактов сборки")
    parser.add_argument("dist", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)

    try:
        project = load_project(ROOT)
        wheel, sdist = find_artifacts(args.dist)
        check_wheel(wheel, project)
        check_sdist(sdist)
        smoke_install(wheel, project.version)
    except CheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {wheel.name} и {sdist.name} проверены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
