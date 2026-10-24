"""Tests for environment configuration and security validation."""

import pytest
from pydantic import ValidationError

from app.core.config import AppEnvironment, Settings


def test_default_settings():
    """Verify default configurations have expected attributes."""
    s = Settings(ENVIRONMENT=AppEnvironment.DEVELOPMENT)
    assert s.APP_NAME == "Inkloom Sentinel API"
    assert s.ENVIRONMENT == AppEnvironment.DEVELOPMENT
    assert s.DEBUG is False
    assert s.is_production is False
    assert s.is_testing is False


def test_database_url_normalization():
    """Verify legacy database URL schemes are normalized to async dialects."""
    s = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db")
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    s2 = Settings(DATABASE_URL="postgres://user:pass@localhost:5432/db")
    assert s2.DATABASE_URL.startswith("postgresql+asyncpg://")

    s3 = Settings(DATABASE_URL="sqlite:///./test.db")
    assert s3.DATABASE_URL.startswith("sqlite+aiosqlite://")


def test_invalid_log_level():
    """Verify invalid log level strings raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings(LOG_LEVEL="SUPER_VERBOSE")


def test_production_security_enforcement():
    """Verify strict validation rules prevent insecure production configurations."""
    # Production cannot have DEBUG=True
    with pytest.raises(ValidationError, match="DEBUG mode must be False"):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=True,
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/prod",
        )

    # Production cannot use default placeholder secret key
    with pytest.raises(
        ValidationError, match="SECRET_KEY must be a cryptographically strong string"
    ):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="change-me-to-a-secure-random-secret-key-at-least-32-chars-long",
            DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/prod",
        )

    # Production cannot use SQLite
    with pytest.raises(ValidationError, match="SQLite is not supported in production"):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="super-secure-production-random-key-1234567890",
            DATABASE_URL="sqlite+aiosqlite:///./test.db",
        )


def test_get_safe_summary_masks_credentials():
    """Verify get_safe_summary hides embedded credentials in database URLs."""
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://admin_user:super_secret_pw@db.internal:5432/inkloom"
    )
    summary = s.get_safe_summary()
    assert "super_secret_pw" not in summary["database_target"]
    assert "***:***@" in summary["database_target"]
    assert "admin_user" not in summary["database_target"]


def test_database_url_sslmode_param_stripped():
    """Verify ?sslmode= is stripped from asyncpg URLs.

    asyncpg silently ignores the ?sslmode= query parameter when it appears in
    the URL string.  The normalizer must remove it so there is no false
    impression that SSL is active when it is not; SSL is applied separately
    via DB_SSL_MODE / connect_args.
    """
    # Supabase-style URL with sslmode=require
    s = Settings(
        DATABASE_URL="postgresql://user:pass@db.supabase.co:5432/postgres?sslmode=require"
    )
    assert "sslmode" not in s.DATABASE_URL
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    # Existing query params other than sslmode must be preserved
    s2 = Settings(
        DATABASE_URL="postgres://user:pass@db.supabase.co:5432/postgres?sslmode=require&connect_timeout=10"
    )
    assert "sslmode" not in s2.DATABASE_URL
    assert "connect_timeout=10" in s2.DATABASE_URL

    # Already-correct asyncpg URL without sslmode should pass through unchanged
    plain = "postgresql+asyncpg://user:pass@localhost:5432/db"
    s3 = Settings(DATABASE_URL=plain)
    assert s3.DATABASE_URL == plain


def test_db_ssl_mode_defaults_empty():
    """Verify DB_SSL_MODE defaults to empty string so local SQLite dev is unaffected."""
    s = Settings()
    assert s.DB_SSL_MODE == ""


def test_cors_origins_parsing():
    """Verify CORS_ORIGINS supports lists, JSON strings, and comma-separated strings."""
    # Default includes Vercel production origin
    s_default = Settings()
    assert "https://inkloom-s.vercel.app" in s_default.CORS_ORIGINS

    # Comma-separated string (common format in cloud dashboard env vars)
    s_csv = Settings(CORS_ORIGINS="https://inkloom-s.vercel.app, https://preview.vercel.app")
    assert s_csv.CORS_ORIGINS == ["https://inkloom-s.vercel.app", "https://preview.vercel.app"]

    # JSON array string
    s_json = Settings(CORS_ORIGINS='["https://inkloom-s.vercel.app", "http://localhost:3000"]')
    assert s_json.CORS_ORIGINS == ["https://inkloom-s.vercel.app", "http://localhost:3000"]

    # Single string
    s_single = Settings(CORS_ORIGINS="https://inkloom-s.vercel.app")
    assert s_single.CORS_ORIGINS == ["https://inkloom-s.vercel.app"]
