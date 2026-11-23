"""Cache-aware parser used by the L2 parse cache (ADR-0020)."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override

from eggpipe.core.document import ModelDocument
from eggpipe.core.format_registry import FormatRegistry
from eggpipe.core.parser import Parser
from eggpipe.engine.document_cache import DocumentCache


class CachedParser(Parser):
    """Parser that serves valid documents from the internal cache."""

    def __init__(self, registry: FormatRegistry, cache: DocumentCache) -> None:
        super().__init__(registry)
        self.cache = cache

    @override
    def parse_document(self, path: Path) -> ModelDocument:
        document = self.cache.load(path)
        if document is not None:
            return document
        document = super().parse_document(path)
        self.cache.remember(path, document)
        return document


__all__ = ["CachedParser"]
