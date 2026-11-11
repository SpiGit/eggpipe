"""Тесты проверки артефактов сборки."""

from __future__ import annotations

from tools.check_wheel import dependency_name, relative_sdist_names


def test_dependency_name_normalizes_distribution_names() -> None:
    assert dependency_name("pydantic>=2.6.0") == "pydantic"
    assert dependency_name("ruamel.yaml>=0.18.6") == "ruamel-yaml"
    assert dependency_name("pydantic-settings; extra == 'dev'") == "pydantic-settings"


def test_relative_sdist_names_strips_root_prefix() -> None:
    names = relative_sdist_names(
        [
            "metadata_generator-0.1.0/pyproject.toml",
            "metadata_generator-0.1.0/src/metadata_generator/__init__.py",
            "metadata_generator-0.1.0",
        ]
    )
    assert names == {
        "pyproject.toml",
        "src/metadata_generator/__init__.py",
    }
