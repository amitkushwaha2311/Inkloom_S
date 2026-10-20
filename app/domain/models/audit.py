"""Inkloom Sentinel - Append-Only Audit Event Model.

Provides an append-only application audit log recording critical domain events
across policies, submissions, verifications, and approvals.

Application-level protection:
- The table omits an `updated_at` column.
- SQLAlchemy event listeners actively reject `before_update` and `before_delete` operations.

Security & Integrity Notice:
- IP addresses are pseudonymized via deterministic SHA-256 hashing for privacy.
- Application-level immutability is enforced at the ORM layer; true cryptographic
  tamper-evidence (e.g., hash chaining or Merkle proofs) and database-level WORM
  storage are not yet implemented and belong to future hardening phases.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    event,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AuditEventType
from app.domain.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """An append-only record of a discrete governance action or event.

    Protected at the ORM level against updates and deletes.
    """

    __tablename__ = "audit_events"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType, native_enum=False), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_snippet: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )


@event.listens_for(AuditEvent, "before_update")
def _prevent_audit_event_update(mapper, connection, target):
    """Prevent application-level modifications to audit event records."""
    raise ValueError("AuditEvent records are append-only: updates are prohibited.")


@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_event_delete(mapper, connection, target):
    """Prevent application-level deletion of audit event records."""
    raise ValueError("AuditEvent records are append-only: deletions are prohibited.")
