from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    service_name: str = "app"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./data/journal.db"
    sqlite_busy_timeout_ms: int = 5000

    storage_backend: str = "local"
    media_root: Path = Path("media")
    output_root: Path = Path("outputs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
