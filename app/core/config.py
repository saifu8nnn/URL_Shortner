import logging
from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pro URL Shortener"
    ENVIRONMENT: str = "development"

    DATABASE_URL: PostgresDsn
    BASE_URL: str = "http://localhost:8000"

    SHORT_CODE_LENGTH: int = 6
    SHORT_CODE_MAX_RETRIES: int = 5

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got '{v}'")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    logger.info(
        "Settings loaded: project=%s env=%s base_url=%s",
        s.PROJECT_NAME,
        s.ENVIRONMENT,
        s.BASE_URL,
    )
    return s


settings = get_settings()