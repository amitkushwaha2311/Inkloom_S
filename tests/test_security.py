"""Tests for foundational security helpers and audit logging service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    constant_time_compare,
    generate_secure_token,
    hash_sensitive_identifier,
)
from app.domain.enums import AuditEventType
from app.domain.models import AuditEvent, BrandWorkspace
from app.services.audit_service import AuditService


def test_security_utilities():
    """Verify cryptographic tokens, timing-safe comparison, and hashing."""
    token = generate_secure_token()
    assert len(token) >= 32

    assert constant_time_compare("secret_string_123", "secret_string_123") is True
    assert constant_time_compare("secret_string_123", "wrong_string") is False

    ip = "192.168.1.100"
    hashed_ip = hash_sensitive_identifier(ip)
    assert hashed_ip is not None
    assert hashed_ip != ip
    assert len(hashed_ip) == 64  # SHA-256 hex digest
    # Deterministic hashing with same salt
    assert hash_sensitive_identifier(ip) == hashed_ip
    # None handling
    assert hash_sensitive_identifier(None) is None


@pytest.mark.asyncio
async def test_audit_service_recording(db_session: AsyncSession):
    """Verify AuditService safely hashes IP addresses and persists events."""
    service = AuditService(session=db_session)

    workspace = BrandWorkspace(name="Audit Test WS", slug="audit-ws")
    db_session.add(workspace)
    await db_session.flush()

    raw_ip = "203.0.113.195"
    raw_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    event = await service.record_event(
        event_type=AuditEventType.CONTENT_SUBMITTED,
        actor_id="user_writer_1",
        resource_type="ContentSubmission",
        resource_id="sub_999",
        event_payload={"word_count": 450, "format": "markdown"},
        workspace_id=workspace.id,
        client_ip=raw_ip,
        user_agent=raw_ua,
    )

    assert event.id is not None
    assert event.ip_address_hash != raw_ip
    assert event.ip_address_hash == hash_sensitive_identifier(raw_ip)
    assert event.user_agent_snippet == raw_ua[:120]

    # Verify query
    result = await db_session.execute(select(AuditEvent).where(AuditEvent.id == event.id))
    fetched = result.scalar_one()
    assert fetched.actor_id == "user_writer_1"
    assert fetched.event_payload["word_count"] == 450


# ---------------------------------------------------------------------------
# Phase 10: Security Headers & Middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_and_traceability(client):
    """Verify that every response includes strict security headers and correlation tracing."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "default-src 'none'" in r.headers.get("Content-Security-Policy", "")
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in r.headers
    assert "X-Process-Time" in r.headers


@pytest.mark.asyncio
async def test_payload_too_large_rejection(client):
    """Verify that requests exceeding the maximum body size are rejected with HTTP 413."""
    oversized_bytes = 10 * 1024 * 1024  # 10 MB > 5 MB limit
    headers = {"Content-Length": str(oversized_bytes), "Content-Type": "application/json"}
    r = await client.post("/api/v1/auth/login", headers=headers, content=b"{}")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ---------------------------------------------------------------------------
# Phase 10: Rate Limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_rate_limiting_enforcement(client):
    """Verify that excessive authentication requests trigger HTTP 429 with Retry-After header."""
    from app.core.config import settings

    max_reqs = settings.AUTH_RATE_LIMIT_MAX_REQUESTS
    endpoint = "/api/v1/auth/login"
    login_body = {"email": "ratelimit_user@example.com", "password": "WrongPassword1"}

    # Issue requests up to the configured limit
    for _ in range(max_reqs):
        r = await client.post(endpoint, json=login_body)
        assert r.status_code == 401  # Normal credential failure, not rate-limited

    # Next request must be blocked by the sliding window rate limiter
    blocked_resp = await client.post(endpoint, json=login_body)
    assert blocked_resp.status_code == 429
    data = blocked_resp.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in blocked_resp.headers
    assert int(blocked_resp.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_expensive_ops_rate_limiter_unit():
    """Unit test sliding window rate limiter window expiration and reset."""
    from app.core.errors import RateLimitExceededError
    from app.core.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter()
    key = "test_expensive_key"

    # Fill to limit of 3
    for _ in range(3):
        await limiter.check_rate_limit(key=key, max_requests=3, window_seconds=10)

    # 4th request must raise RateLimitExceededError
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check_rate_limit(key=key, max_requests=3, window_seconds=10)
    assert exc_info.value.retry_after >= 1

    # Reset clears tracking
    await limiter.reset()
    # Now it succeeds again without error
    await limiter.check_rate_limit(key=key, max_requests=3, window_seconds=10)


# ---------------------------------------------------------------------------
# Phase 10: SSRF Protection
# ---------------------------------------------------------------------------


def test_ssrf_url_validation_comprehensive():
    """Verify SSRF validation blocks private IPs, metadata endpoints, and alternate IP encodings."""
    from app.core.errors import ValidationError
    from app.core.ssrf import validate_safe_url

    # Permitted public URLs
    assert validate_safe_url("https://example.com/regulatory/standard.pdf") is not None
    assert validate_safe_url("http://brand-guidelines.external.org/spec") is not None
    assert validate_safe_url(None) is None
    assert validate_safe_url("") is None

    # Blocked schemes
    with pytest.raises(ValidationError, match="Unsupported URL scheme"):
        validate_safe_url("ftp://example.com/file")
    with pytest.raises(ValidationError, match="Unsupported URL scheme"):
        validate_safe_url("file:///etc/passwd")
    with pytest.raises(ValidationError, match="Unsupported URL scheme"):
        validate_safe_url("gopher://127.0.0.1:70")

    # Blocked loopbacks & local hostnames
    with pytest.raises(ValidationError, match="not permitted"):
        validate_safe_url("http://localhost:8000/api")
    with pytest.raises(ValidationError, match="not permitted"):
        validate_safe_url("http://service.local/data")
    with pytest.raises(ValidationError, match="not permitted"):
        validate_safe_url("http://metadata.google.internal/computeMetadata/v1/")

    # Blocked explicit IPv4 private and link-local ranges
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://127.0.0.1:8000/secret")
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://10.0.0.5/admin")
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://172.16.0.1/internal")
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://192.168.1.1/router")
    with pytest.raises(ValidationError):
        validate_safe_url("http://169.254.169.254/latest/meta-data/")

    # Blocked decimal integer IP representation (e.g., 2130706433 = 127.0.0.1)
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://2130706433/")

    # Blocked IPv6 loopback
    with pytest.raises(ValidationError, match="private, loopback, or restricted"):
        validate_safe_url("http://[::1]/secret")


# ---------------------------------------------------------------------------
# Phase 10: Production Configuration Validation
# ---------------------------------------------------------------------------


def test_production_environment_security_checks():
    """Verify Settings rejects insecure development configurations in production mode."""
    from app.core.config import AppEnvironment, Settings

    # Production with DEBUG=True must be rejected
    with pytest.raises(ValueError, match="DEBUG mode must be False in production"):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=True,
            SECRET_KEY="a-very-long-and-secure-random-token-32-chars!!",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/prod_db",
        )

    # Production with default/weak SECRET_KEY must be rejected
    with pytest.raises(ValueError, match="SECRET_KEY must be a cryptographically strong string"):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="short-secret",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/prod_db",
        )

    # Production with SQLite must be rejected
    with pytest.raises(ValueError, match="SQLite is not supported in production"):
        Settings(
            ENVIRONMENT=AppEnvironment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="a-very-long-and-secure-random-token-32-chars!!",
            DATABASE_URL="sqlite+aiosqlite:///./prod.db",
        )

    # Production with valid settings passes
    prod_settings = Settings(
        ENVIRONMENT=AppEnvironment.PRODUCTION,
        DEBUG=False,
        SECRET_KEY="a-properly-randomized-32-character-production-token!!",
        DATABASE_URL="postgresql+asyncpg://app_user:strong_password@prod-db.internal:5432/inkloom",
    )
    assert prod_settings.is_production is True
    assert prod_settings.DEBUG is False
    safe_summary = prod_settings.get_safe_summary()
    assert "***:***" in safe_summary["database_target"]  # Credentials masked


# ---------------------------------------------------------------------------
# Phase 10: Refresh Token Rotation & Replay Attack Defense
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_replay_protection(client):
    """Verify refresh token rotation and that replaying an old refresh token is strictly rejected."""
    email = "token_replay_test@example.com"
    pwd = "SecurePassword1"

    # Register
    r_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "full_name": "Replay Tester"},
    )
    assert r_reg.status_code == 201

    # Login -> get Token Pair 1
    r_login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert r_login.status_code == 200
    token_pair_1 = r_login.json()
    refresh_1 = token_pair_1["refresh_token"]

    # Refresh with Token 1 -> get Token Pair 2 (Token 1 is now revoked)
    r_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert r_refresh.status_code == 200
    token_pair_2 = r_refresh.json()
    refresh_2 = token_pair_2["refresh_token"]
    assert refresh_2 != refresh_1

    # REPLAY ATTACK: Attempt to use refresh_1 again
    r_replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert r_replay.status_code == 401
    assert "revoked" in r_replay.json()["error"]["message"].lower()

    # Logout with Token 2
    auth_header = {"Authorization": f"Bearer {token_pair_2['access_token']}"}
    r_logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_2},
        headers=auth_header,
    )
    assert r_logout.status_code == 204

    # Attempt refresh after logout
    r_after_logout = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_2})
    assert r_after_logout.status_code == 401


# ---------------------------------------------------------------------------
# Phase 10: Cross-Tenant Workspace Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_workspace_isolation(client):
    """Verify that a user from Tenant B cannot access Tenant A's workspace or policies."""
    # User A creates Workspace A
    r_reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_a@example.com", "password": "Password1", "full_name": "Tenant A"},
    )
    assert r_reg_a.status_code == 201
    r_login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "tenant_a@example.com", "password": "Password1"},
    )
    token_a = r_login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    r_ws_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "Tenant A Workspace"},
        headers=headers_a,
    )
    assert r_ws_a.status_code == 201
    ws_a_id = r_ws_a.json()["id"]

    # User B registers
    r_reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_b@example.com", "password": "Password1", "full_name": "Tenant B"},
    )
    assert r_reg_b.status_code == 201
    r_login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "tenant_b@example.com", "password": "Password1"},
    )
    token_b = r_login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B tries to read Workspace A
    r_forbidden_get = await client.get(f"/api/v1/workspaces/{ws_a_id}", headers=headers_b)
    assert r_forbidden_get.status_code == 403

    # User B tries to list policies in Workspace A
    r_forbidden_policies = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/policies",
        headers=headers_b,
    )
    assert r_forbidden_policies.status_code == 403

    # User B tries to access audit logs in Workspace A
    r_forbidden_audit = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/audit-events",
        headers=headers_b,
    )
    assert r_forbidden_audit.status_code == 403

