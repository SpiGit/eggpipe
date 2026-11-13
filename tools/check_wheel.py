#!/usr/bin/env python3
"""Check wheel/sdist artifacts and smoke-install the built package.

Usage:
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
    "eggpipe/__init__.py",
    "eggpipe/py.typed",
}
REQUIRED_SDIST_FILES = {
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/eggpipe/__init__.py",
    "src/eggpipe/py.typed",
}
REQUIRED_DEPENDENCIES = {
    "typer",
    "pydantic",
    "pydantic-settings",
    "ruamel-yaml",
    "rich",
}


class CheckError(RuntimeError):
    """Artifact check error."""


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
        raise CheckError(f"failed to read {path}: {exc}") from exc

    project = raw.get("project")
    if not isinstance(project, dict):
        raise CheckError("pyproject.toml has no [project] section")

    name = project.get("name")
    version = project.get("version")
    requires_python = project.get("requires-python")
    if not all(isinstance(value, str) for value in (name, version, requires_python)):
        raise CheckError("project.name, project.version and project.requires-python are required")
    assert isinstance(name, str)
    assert isinstance(version, str)
    assert isinstance(requires_python, str)
    return Project(name=name, version=version, requires_python=requires_python)


def find_artifacts(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise CheckError(
            f"expected exactly one wheel and one sdist in {dist}, "
            f"found: {len(wheels)} wheel(s), {len(sdists)} sdist(s)"
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
        raise CheckError("wheel has no METADATA")
    try:
        text = archive.read(metadata_name).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError(f"METADATA is not UTF-8: {exc}") from exc
    message = Parser().parsestr(text, headersonly=True)
    if message.get("Version") != version:
        raise CheckError(
            f"version in METADATA does not match: {message.get('Version')} != {version}"
        )
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
            raise CheckError(f"{field} in METADATA: {message.get(field)!r} != {value!r}")

    requires = message.get_all("Requires-Dist") or []
    required_names = {
        dependency_name(requirement) for requirement in requires if "extra ==" not in requirement
    }
    missing = REQUIRED_DEPENDENCIES - required_names
    if missing:
        raise CheckError(f"METADATA is missing required dependencies: {sorted(missing)}")

    extras = set(message.get_all("Provides-Extra") or [])
    for extra in ("dev", "watch"):
        if extra not in extras:
            raise CheckError(f"METADATA is missing extra {extra!r}")


def check_wheel(path: Path, project: Project) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = REQUIRED_WHEEL_FILES - names
        if missing:
            raise CheckError(f"wheel is missing files: {sorted(missing)}")
        forbidden = sorted(name for name in names if name.startswith(("tests/", "docs/")))
        if forbidden:
            raise CheckError(f"wheel contains dev files: {forbidden}")
        message = metadata_from_wheel(archive, project.version)
        check_metadata(message, project)
        if not any(name.endswith("/licenses/LICENSE") for name in names):
            raise CheckError("wheel has no LICENSE")
        entry_points = next(
            (name for name in names if name.endswith(".dist-info/entry_points.txt")),
            None,
        )
        if entry_points is None:
            raise CheckError("wheel has no entry_points.txt")
        text = archive.read(entry_points).decode("utf-8")
        if "eggpipe = eggpipe.cli.main:app" not in text:
            raise CheckError("wheel has no eggpipe console script")


def check_sdist(path: Path) -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            names = relative_sdist_names(archive.getnames())
    except (OSError, tarfile.TarError) as exc:
        raise CheckError(f"failed to read sdist {path}: {exc}") from exc

    missing = REQUIRED_SDIST_FILES - names
    if missing:
        raise CheckError(f"sdist is missing files: {sorted(missing)}")
    forbidden = sorted(name for name in names if name.startswith((".github/", ".opencode/")))
    if forbidden:
        raise CheckError(f"sdist contains dev files: {forbidden}")


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
            "failed to install the wheel",
        )
        run_checked(
            [
                str(python),
                "-c",
                f"import eggpipe; assert eggpipe.__version__ == {version!r}",
            ],
            "the wheel does not import or the version does not match",
        )
        script = environment / ("Scripts/eggpipe.exe" if sys.platform == "win32" else "bin/eggpipe")
        run_checked([str(script), "--help"], "the eggpipe console script does not work")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check build artifacts")
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

    print(f"OK: {wheel.name} and {sdist.name} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
