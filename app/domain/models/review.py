"""Inkloom Sentinel - Review, Approval Decision, & Correction Models.

Captures:
- Formal human governance determinations rendered on verified content drafts (ReviewDecision).
- Structured correction suggestions associated with findings and evidence (CorrectionSuggestion).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CorrectionStatus, ReviewDecisionType
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.evidence import EvidenceSource
    from app.domain.models.policy import BrandPolicy, PolicyGuideline
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
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brand_policies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[ReviewDecisionType] = mapped_column(
        SAEnum(ReviewDecisionType, native_enum=False), nullable=False, index=True
    )
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    submission: Mapped["ContentSubmission"] = relationship(
        "ContentSubmission", back_populates="review_decisions"
    )
    revision: Mapped["ContentRevision"] = relationship(
        "ContentRevision", back_populates="review_decisions"
    )
    policy: Mapped[Optional["BrandPolicy"]] = relationship("BrandPolicy", lazy="selectin")


class CorrectionSuggestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A structured correction suggestion linked to a finding or guideline."""

    __tablename__ = "correction_suggestions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    guideline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_guidelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_replacement: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CorrectionStatus] = mapped_column(
        SAEnum(CorrectionStatus, native_enum=False),
        default=CorrectionStatus.PROPOSED,
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applied_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    revision: Mapped["ContentRevision"] = relationship(
        "ContentRevision", foreign_keys=[revision_id], lazy="selectin"
    )
    guideline: Mapped[Optional["PolicyGuideline"]] = relationship(
        "PolicyGuideline", lazy="selectin"
    )
    evidence_source: Mapped[Optional["EvidenceSource"]] = relationship(
        "EvidenceSource", lazy="selectin"
    )
