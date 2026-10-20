"""Inkloom Sentinel - Database Infrastructure & Connectivity.

Async SQLAlchemy 2.0 database engine, session factory,
and health check utilities supporting both PostgreSQL and SQLite.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_engine(database_url: str | None = None) -> AsyncEngine:
    """Construct an async SQLAlchemy engine with environment-appropriate pooling."""
    url = database_url or settings.DATABASE_URL
    is_sqlite = url.startswith("sqlite")

    engine_kwargs: dict[str, Any] = {
        "echo": settings.DB_ECHO,
        "future": True,
    }

    if is_sqlite:
        # SQLite async engine configuration
        # SQLite does not support standard server connection pools
        pass
    else:
        # PostgreSQL / asyncpg connection pool configuration
        engine_kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_pre_ping": True,
            }
        )

    return create_async_engine(url, **engine_kwargs)


# Global engine and sessionmaker
engine: AsyncEngine = build_engine()
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding transactional database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> dict[str, Any]:
    """Execute a lightweight probe to verify database connectivity.

    Returns non-sensitive health metadata without leaking connection strings.
    """
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "healthy": True,
            "latency_ms": latency_ms,
            "dialect": engine.dialect.name,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "database_health_check_failed",
            error=str(exc.__class__.__name__),
            latency_ms=latency_ms,
        )
        return {
            "healthy": False,
            "latency_ms": latency_ms,
            "dialect": engine.dialect.name,
            "error": "Database connectivity check failed",
        }


async def close_db_engine() -> None:
    """Gracefully dispose of all engine connections."""
    await engine.dispose()
    logger.info("database_engine_disposed")
