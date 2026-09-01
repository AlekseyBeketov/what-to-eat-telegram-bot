from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr = Field(validation_alias=AliasChoices("BOT_TOKEN", "API_KEY"))
    database_path: Path = Field(default=Path("data/what_to_eat.sqlite3"), alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    invite_ttl_hours: int = Field(default=72, ge=1, le=24 * 30, alias="INVITE_TTL_HOURS")
    bot_username: str = Field(default="", alias="BOT_USERNAME")

    @field_validator("bot_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("BOT_TOKEN is required")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("bot_username")
    @classmethod
    def strip_at(cls, value: str) -> str:
        return value.strip().lstrip("@")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
