"""Inkloom Sentinel - Semantic Review & Guideline Interpretation Models.

Domain entities for:
- SemanticReviewRun: Auditable execution of semantic guideline evaluations on a revision against a policy.
- SemanticReviewFinding: Discrete semantic findings with uncertainty, rationale, and character spans.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import FindingCategory, SemanticOutcome
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.policy import BrandPolicy, PolicyGuideline
    from app.domain.models.submission import ContentRevision


class SemanticReviewRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An immutable record of a contextual semantic review against brand guidelines."""

    __tablename__ = "semantic_review_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    overall_outcome: Mapped[SemanticOutcome] = mapped_column(
        SAEnum(SemanticOutcome, native_enum=False),
        nullable=False,
        index=True,
    )
    total_guidelines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    violation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inconclusive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(
        String(64), default="sentinel-semantic-v1.0", nullable=False
    )
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    revision: Mapped["ContentRevision"] = relationship("ContentRevision", lazy="selectin")
    policy: Mapped["BrandPolicy"] = relationship("BrandPolicy", lazy="selectin")
    findings: Mapped[list["SemanticReviewFinding"]] = relationship(
        "SemanticReviewFinding",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SemanticReviewFinding(Base, UUIDPrimaryKeyMixin):
    """An individual contextual finding produced by semantic guideline evaluation."""

    __tablename__ = "semantic_review_findings"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guideline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_guidelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(
        SAEnum(FindingCategory, native_enum=False), nullable=False, index=True
    )
    outcome: Mapped[SemanticOutcome] = mapped_column(
        SAEnum(SemanticOutcome, native_enum=False), nullable=False, index=True
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    flagged_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    run: Mapped["SemanticReviewRun"] = relationship("SemanticReviewRun", back_populates="findings")
    guideline: Mapped[Optional["PolicyGuideline"]] = relationship(
        "PolicyGuideline", lazy="selectin"
    )
