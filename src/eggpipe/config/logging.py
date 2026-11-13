"""Единая точка настройки логирования CLI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from eggpipe.config.app_config import AppConfig

LOGGER_NAME = "eggpipe"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def setup_logging(config: AppConfig) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    if config.log_destination.startswith("file:"):
        path = Path(config.log_destination.removeprefix("file:"))
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(path, encoding="utf-8")
    elif config.log_destination == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(config.log_format))
    logger.addHandler(handler)
    return logger


__all__ = ["LOGGER_NAME", "get_logger", "setup_logging"]
