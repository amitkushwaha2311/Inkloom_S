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
