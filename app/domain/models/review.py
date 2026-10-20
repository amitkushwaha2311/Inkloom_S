"""Inkloom Sentinel - Review & Approval Decision Models.

Captures formal human governance determinations rendered on verified content drafts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ReviewDecisionType
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.submission import ContentRevision, ContentSubmission


class ReviewDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An explicit human review determination on a content revision."""

    __tablename__ = "review_decisions"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[ReviewDecisionType] = mapped_column(
        SAEnum(ReviewDecisionType, native_enum=False), nullable=False, index=True
    )
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    submission: Mapped["ContentSubmission"] = relationship("ContentSubmission", back_populates="review_decisions")
    revision: Mapped["ContentRevision"] = relationship("ContentRevision", back_populates="review_decisions")
