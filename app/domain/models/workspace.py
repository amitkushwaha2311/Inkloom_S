"""Inkloom Sentinel - Workspace & Membership Models.

Defines the tenancy boundary for brand workspaces and associated collaborator roles.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import WorkspaceRole
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.policy import BrandPolicy
    from app.domain.models.submission import ContentSubmission


class BrandWorkspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents an isolated organizational workspace governing one or more brand profiles."""

    __tablename__ = "brand_workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    policies: Mapped[list["BrandPolicy"]] = relationship(
        "BrandPolicy", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    submissions: Mapped[list["ContentSubmission"]] = relationship(
        "ContentSubmission", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkspaceMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Associates an authenticated user with a workspace and an assigned role."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_user"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, native_enum=False), default=WorkspaceRole.CONTRIBUTOR, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    workspace: Mapped["BrandWorkspace"] = relationship("BrandWorkspace", back_populates="members")
