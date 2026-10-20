"""Inkloom Sentinel - Foundational Audit Service.

Provides an append-only interface for recording domain events and compliance actions.
Ensures sensitive user client data (like IP) is safely hashed before persistence.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_sensitive_identifier
from app.domain.enums import AuditEventType
from app.domain.models.audit import AuditEvent

logger = get_logger(__name__)


class AuditService:
    """Service governing immutable, append-only domain event logging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        event_payload: dict[str, Any],
        workspace_id: uuid.UUID | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Create and persist an immutable audit event entry."""
        # Privacy-preserving hash of client IP
        ip_hash = hash_sensitive_identifier(client_ip) if client_ip else None
        ua_snippet = user_agent[:120] if user_agent else None

        event = AuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_payload=event_payload,
            ip_address_hash=ip_hash,
            user_agent_snippet=ua_snippet,
        )

        self.session.add(event)
        # Flush to generate ID and timestamp without committing the outer transaction prematurely
        await self.session.flush()

        logger.info(
            "audit_event_recorded",
            event_type=event_type.value,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            audit_id=str(event.id),
        )
        return event
