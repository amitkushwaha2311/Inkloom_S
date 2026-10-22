"""Inkloom Sentinel - Test Configuration & Fixtures.

Sets up isolated async test environment using in-memory SQLite
and provides httpx.AsyncClient fixtures for testing the FastAPI application.

Phase 3 additions:
- auth_client fixture: registers a user and injects a valid Bearer token
- make_user / make_token helpers shared across test modules
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure test environment before any app module imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-chars-long-for-testing"
os.environ["LOG_LEVEL"] = "WARNING"

from app.core.database import get_db_session
from app.domain.models import Base
from app.main import app

# Test engine bound to in-memory SQLite
test_engine: AsyncEngine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all domain tables before each test and drop them afterward."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_rate_limiters() -> AsyncGenerator[None, None]:
    """Reset rate limiter state before and after each test."""
    from app.core.rate_limit import auth_rate_limiter, expensive_ops_limiter

    await auth_rate_limiter.reset()
    await expensive_ops_limiter.reset()
    yield
    await auth_rate_limiter.reset()
    await expensive_ops_limiter.reset()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated transactional database session."""
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client fixture with overridden database dependency."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helper fixtures
# ---------------------------------------------------------------------------

_DEFAULT_EMAIL = "alice@example.com"
_DEFAULT_PASSWORD = "TestPass1"


async def register_and_login(
    client: AsyncClient,
    email: str = _DEFAULT_EMAIL,
    password: str = _DEFAULT_PASSWORD,
    full_name: str = "Alice Test",
) -> dict:
    """Register a user and return the token response dict."""
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    r2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    return r2.json()


@pytest_asyncio.fixture
async def auth_tokens(client: AsyncClient) -> dict:
    """Register default user and return token response."""
    return await register_and_login(client)


@pytest_asyncio.fixture
async def auth_headers(auth_tokens: dict) -> dict:
    """Return Authorization headers for the default user."""
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


async def create_workspace_with_owner(
    client: AsyncClient,
    headers: dict,
    name: str = "Test Workspace",
) -> dict:
    """Create a workspace and return its JSON."""
    r = await client.post(
        "/api/v1/workspaces",
        json={"name": name},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()
