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

        # asyncpg does NOT honour the ?sslmode= query-string parameter.
        # SSL must be supplied through connect_args.  DB_SSL_MODE can be set
        # explicitly (e.g. "require") or auto-detected from the original URL.
        ssl_mode = settings.DB_SSL_MODE.strip().lower()
        if ssl_mode:
            engine_kwargs["connect_args"] = {"ssl": ssl_mode}
            logger.debug(
                "asyncpg_ssl_connect_args_applied",
                ssl_mode=ssl_mode,
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

        # Build a safe cause chain (asyncpg strips credentials from messages).
        cause_chain: list[str] = []
        current: BaseException | None = exc
        while current is not None:
            cause_chain.append(f"{type(current).__qualname__}: {current}")
            current = current.__cause__ or current.__context__
            if len(cause_chain) >= 5:  # guard against circular refs
                break

        logger.error(
            "database_health_check_failed",
            error=type(exc).__qualname__,
            # asyncpg exception messages never contain the connection URL or
            # password; it is safe to log str(exc) directly here.
            error_detail=str(exc),
            error_cause_chain=cause_chain,
            ssl_mode=settings.DB_SSL_MODE or "(none)",
            dialect=engine.dialect.name,
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
