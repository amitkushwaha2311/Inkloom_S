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
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event.id)
    )
    fetched = result.scalar_one()
    assert fetched.actor_id == "user_writer_1"
    assert fetched.event_payload["word_count"] == 450
