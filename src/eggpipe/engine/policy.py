"""Diagnostic filtering policy."""

from __future__ import annotations

from dataclasses import dataclass

from eggpipe.interfaces.diagnostics import Diagnostic


@dataclass(frozen=True)
class DiagnosticPolicy:
    ignore: frozenset[str] = frozenset()
    strict: bool = False

    def apply(self, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
        filtered = [
            item for item in diagnostics if item.level == "error" or item.code not in self.ignore
        ]
        if not self.strict:
            return filtered
        return [
            item.model_copy(update={"level": "error"}) if item.level == "warning" else item
            for item in filtered
        ]


__all__ = ["DiagnosticPolicy"]
