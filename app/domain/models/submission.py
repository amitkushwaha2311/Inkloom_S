"""Inkloom Sentinel - Content Submission & Revision Models.

Captures drafts submitted for brand compliance checks and their
immutable revision history.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import SubmissionStatus
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.review import ReviewDecision
    from app.domain.models.verification import VerificationFinding
    from app.domain.models.workspace import BrandWorkspace


class ContentSubmission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A content item subject to brand governance review."""

    __tablename__ = "content_submissions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, native_enum=False), default=SubmissionStatus.DRAFT, nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relationships
    workspace: Mapped["BrandWorkspace"] = relationship("BrandWorkspace", back_populates="submissions")
    revisions: Mapped[list["ContentRevision"]] = relationship(
        "ContentRevision", back_populates="submission", cascade="all, delete-orphan", order_by="ContentRevision.revision_number", lazy="selectin"
    )
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(
        "ReviewDecision", back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )


class ContentRevision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An immutable versioned snapshot of content submitted for verification."""

    __tablename__ = "content_revisions"
    __table_args__ = (
        UniqueConstraint("submission_id", "revision_number", name="uq_submission_revision_number"),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(String(32), default="markdown", nullable=False)
    metadata_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    submission: Mapped["ContentSubmission"] = relationship("ContentSubmission", back_populates="revisions")
    findings: Mapped[list["VerificationFinding"]] = relationship(
        "VerificationFinding", back_populates="revision", cascade="all, delete-orphan", lazy="selectin"
    )
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(
        "ReviewDecision", back_populates="revision", lazy="selectin"
    )
