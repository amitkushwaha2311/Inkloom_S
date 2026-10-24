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
        "https://inkloom-s.vercel.app",
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
    # SSL mode for asyncpg connections (e.g. "require", "prefer", "disable").
    # asyncpg does NOT honour the ?sslmode= query parameter in the URL; this
    # setting is passed via connect_args instead.  Set to "require" for any
    # Supabase / RDS / managed-PostgreSQL provider that enforces TLS.
    DB_SSL_MODE: str = ""

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Ensure async driver dialect is specified for SQLAlchemy async engine.

        Also strips the ``?sslmode=`` query parameter from PostgreSQL URLs.
        asyncpg silently ignores this parameter when it appears in the URL
        string; SSL must be configured via ``connect_args`` (see
        ``build_engine`` in ``database.py``).  Stripping it here prevents
        the false impression that SSL is active when it is not.
        """
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("sqlite://") and not v.startswith("sqlite+aiosqlite://"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)

        # Strip sslmode from URL query string for asyncpg URLs.
        # The sslmode= param is only meaningful for libpq / psycopg2; asyncpg
        # requires the SSL policy to be passed via connect_args, not the URL.
        if "postgresql+asyncpg://" in v and "sslmode=" in v:
            from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

            parts = urlsplit(v)
            qs = parse_qs(parts.query, keep_blank_values=True)
            qs.pop("sslmode", None)  # remove the offending param
            new_query = urlencode({k: v2[0] for k, v2 in qs.items()})
            v = urlunsplit(parts._replace(query=new_query))

        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in allowed:
            raise ValueError(f"Invalid LOG_LEVEL '{v}'. Allowed: {', '.join(allowed)}")
        return upper_v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Support JSON array string, comma-separated string, or list of origins."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: str | list[str]) -> list[str]:
        """Support JSON array string, comma-separated string, or list of hosts."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

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
