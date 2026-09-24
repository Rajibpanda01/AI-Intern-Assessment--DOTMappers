from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "Support Ticket AI"
    data_path: str = "data/support_tickets.csv"
    # Ollama is free and local. The service still degrades to grounded rules when
    # the model is unavailable so the API remains runnable for smoke tests.
    llm_provider: Literal["none", "ollama", "openai-compatible"] = "ollama"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = Field(default=None, repr=False)
    request_timeout_seconds: float = 3.0
    max_evidence_items: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
