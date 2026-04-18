"""
Application settings loaded from environment variables.

All configuration is centralized here so every module reads
from a single source of truth.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    # ── LLM ──────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7

    # ── Serper API (mandatory web-search tool) ───────────
    serper_api_key: str = ""

    # ── Application ──────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── Workflow limits ──────────────────────────────────
    max_revisions: int = 3


@lru_cache()
def get_settings() -> Settings:
    """Return a cached *Settings* instance built from env vars."""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
        serper_api_key=os.getenv("SERPER_API_KEY", ""),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_revisions=int(os.getenv("MAX_REVISIONS", "3")),
    )
