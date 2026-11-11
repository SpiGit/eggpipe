"""Загрузка генераторов из entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

from metadata_generator.interfaces.generator import GeneratorPlugin

GENERATOR_GROUP = "metadata_generator.generators"


def load_generators() -> dict[str, GeneratorPlugin]:
    result: dict[str, GeneratorPlugin] = {}
    for entry_point in entry_points(group=GENERATOR_GROUP):
        try:
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
        except Exception:
            continue
        if not isinstance(plugin, GeneratorPlugin):
            continue
        if plugin.api_version != "1":
            continue
        config_id = plugin.id
        if entry_point.name != config_id:
            continue
        result[config_id] = plugin
    return result


__all__ = ["GENERATOR_GROUP", "load_generators"]
