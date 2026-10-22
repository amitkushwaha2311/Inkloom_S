"""Inkloom Sentinel - Application Configuration & Settings.

Environment-based configuration managed via Pydantic Settings.
Safe defaults are provided for local development, while production
enforces strict security requirements.
"""

from enum import Enum

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Identity
    APP_NAME: str = "Inkloom Sentinel API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: AppEnvironment = AppEnvironment.DEVELOPMENT
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Server Binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Security & Secrets
    SECRET_KEY: str = "change-me-to-a-secure-random-secret-key-at-least-32-chars-long"
    ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost", "testserver"]
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Rate Limiting & DoS Protection
    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = 20
    VERIFY_RATE_LIMIT_MAX_REQUESTS: int = 60
    MAX_REQUEST_BODY_BYTES: int = 5 * 1024 * 1024  # 5 MB max body size

    # JWT Token Settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///./inkloom_sentinel.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Ensure async driver dialect is specified for SQLAlchemy async engine."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("sqlite://") and not v.startswith("sqlite+aiosqlite://"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in allowed:
            raise ValueError(f"Invalid LOG_LEVEL '{v}'. Allowed: {', '.join(allowed)}")
        return upper_v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce strict security constraints when running in production."""
        if self.ENVIRONMENT == AppEnvironment.PRODUCTION:
            if self.DEBUG:
                raise ValueError("DEBUG mode must be False in production environment")
            if (
                len(self.SECRET_KEY) < 32
                or "change-me" in self.SECRET_KEY.lower()
                or "secret" in self.SECRET_KEY.lower()
            ):
                raise ValueError(
                    "SECRET_KEY must be a cryptographically strong string of at least 32 characters in production"
                )
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "SQLite is not supported in production. Configure a production-grade PostgreSQL DATABASE_URL."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == AppEnvironment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == AppEnvironment.TEST

    def get_safe_summary(self) -> dict:
        """Return non-sensitive configuration values safe for diagnostics."""
        # Mask database URL credentials
        db_url_safe = self.DATABASE_URL
        if "@" in db_url_safe:
            # Mask user:pass@host
            scheme_and_auth, rest = db_url_safe.split("@", 1)
            scheme = scheme_and_auth.split("://")[0]
            db_url_safe = f"{scheme}://***:***@{rest}"

        return {
            "app_name": self.APP_NAME,
            "version": self.APP_VERSION,
            "environment": self.ENVIRONMENT.value,
            "debug": self.DEBUG,
            "api_v1_prefix": self.API_V1_PREFIX,
            "database_driver": self.DATABASE_URL.split("://")[0],
            "database_target": db_url_safe,
            "log_level": self.LOG_LEVEL,
            "log_json_format": self.LOG_JSON_FORMAT,
        }


settings = Settings()
