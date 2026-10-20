"""Inkloom Sentinel - Append-Only Audit Event Model.

Provides an immutable, tamper-evident record of all critical domain events
across policies, submissions, verifications, and approvals.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AuditEventType
from app.domain.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """An immutable, append-only record of a discrete governance action or event.

    Notice this table intentionally omits an `updated_at` column to reflect
    its immutable, append-only nature.
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
