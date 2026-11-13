"""Техническая конфигурация приложения."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EGGPIPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_destination: str = "stderr"

    rules_file: Path | None = None
    output_root: Path | None = None
    force: bool = False
    include_disabled: bool = False
    allow_outside_imports: bool = False
    clean: bool = False
    debug: bool = False
    verbose: bool = False
    quiet: bool = False
    watch_debounce_ms: int = 300


__all__ = ["AppConfig"]
