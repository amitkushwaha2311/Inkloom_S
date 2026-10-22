"""Inkloom Sentinel - User Account & Refresh Token Models.

Stores local account credentials, email-based identity, and
server-side refresh token records for secure JWT revocation.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    pass


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Authenticated application user with local email/password credentials."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True once the user has confirmed their email address",
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """Server-side refresh token record for revocation and replay detection.

    The raw token string is NEVER stored — only its SHA-256 hex digest.
    This prevents privilege escalation if the table is read by an attacker.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex digest of the raw opaque token string",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    # Store a hint (first 8 chars of the token) for client-side debugging — never the full token
    hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Non-sensitive metadata
    user_agent_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
