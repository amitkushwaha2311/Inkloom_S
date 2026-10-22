"""Inkloom Sentinel - Evidence Source and Claim Verification Models.

Provides domain entities for:
- EvidenceSource: Approved authoritative documentation registry with validity dates and versioning.
- ContentClaim: Structured claim representations extracted from or submitted against content revisions.
- ClaimAssessment: Immutable evidence-backed claim verification results.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
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

from app.domain.enums import (
    ClaimAssessmentStatus,
    ClaimDiscoveryStatus,
    ClaimType,
    EvidenceSourceType,
    SourceApprovalStatus,
)
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.domain.models.policy import BrandPolicy
    from app.domain.models.submission import ContentRevision
    from app.domain.models.workspace import BrandWorkspace


class EvidenceSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An approved or registered authoritative evidence source within a workspace."""

    __tablename__ = "evidence_sources"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[EvidenceSourceType] = mapped_column(
        SAEnum(EvidenceSourceType, native_enum=False), nullable=False, index=True
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    internal_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher_or_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_status: Mapped[SourceApprovalStatus] = mapped_column(
        SAEnum(SourceApprovalStatus, native_enum=False),
        default=SourceApprovalStatus.DRAFT,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trusted_excerpts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    structured_facts: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    workspace: Mapped["BrandWorkspace"] = relationship("BrandWorkspace", lazy="selectin")

    def is_currently_valid(self, when: datetime | None = None) -> bool:
        """Return True only if source is APPROVED and not expired at `when`."""
        if self.approval_status != SourceApprovalStatus.APPROVED:
            return False
        if self.expiry_date is None:
            return True
        ref_time = when or datetime.now(UTC)
        exp = self.expiry_date
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=UTC)
        if exp < ref_time:
            return False
        return True


class ContentClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A discrete assertion or statement made within a specific content revision."""

    __tablename__ = "content_claims"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(
        SAEnum(ClaimType, native_enum=False),
        default=ClaimType.FACTUAL,
        nullable=False,
        index=True,
    )
    context_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discovery_status: Mapped[ClaimDiscoveryStatus] = mapped_column(
        SAEnum(ClaimDiscoveryStatus, native_enum=False),
        default=ClaimDiscoveryStatus.CANDIDATE,
        nullable=False,
        index=True,
    )
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    revision: Mapped["ContentRevision"] = relationship("ContentRevision", back_populates="claims")
    assessments: Mapped[list["ClaimAssessment"]] = relationship(
        "ClaimAssessment",
        back_populates="claim",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ClaimAssessment.created_at.desc()",
    )


class ClaimAssessment(Base, UUIDPrimaryKeyMixin):
    """An immutable evidence-backed assessment outcome for a specific content claim."""

    __tablename__ = "claim_assessments"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brand_policies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_status: Mapped[ClaimAssessmentStatus] = mapped_column(
        SAEnum(ClaimAssessmentStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_version: Mapped[str] = mapped_column(
        String(64), default="sentinel-claim-v1.0", nullable=False
    )
    assessed_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    supporting_sources_snapshot: Mapped[list[dict]] = mapped_column(
        JSON, default=list, nullable=False
    )
    contradicting_sources_snapshot: Mapped[list[dict]] = mapped_column(
        JSON, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    claim: Mapped["ContentClaim"] = relationship("ContentClaim", back_populates="assessments")
    revision: Mapped["ContentRevision"] = relationship("ContentRevision", lazy="selectin")
    policy: Mapped[Optional["BrandPolicy"]] = relationship("BrandPolicy", lazy="selectin")
