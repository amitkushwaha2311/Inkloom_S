"""Inkloom Sentinel - Verification Findings & Evidence References Models.

Domain entities representing concrete compliance issues flagged during checks
along with verifiable evidence references backing each finding.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EvidenceReferenceType, FindingCategory, SeverityLevel
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.models.policy import PolicyGuideline
    from app.domain.models.submission import ContentRevision


class VerificationFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A detected brand or compliance issue in a specific content revision."""

    __tablename__ = "verification_findings"

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guideline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_guidelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(
        SAEnum(FindingCategory, native_enum=False), nullable=False, index=True
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel, native_enum=False), default=SeverityLevel.MEDIUM, nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    flagged_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    revision: Mapped["ContentRevision"] = relationship("ContentRevision", back_populates="findings")
    guideline: Mapped[Optional["PolicyGuideline"]] = relationship("PolicyGuideline", lazy="selectin")
    evidence_references: Mapped[list["EvidenceReference"]] = relationship(
        "EvidenceReference", back_populates="finding", cascade="all, delete-orphan", lazy="selectin"
    )


class EvidenceReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An authoritative citation or guideline excerpt proving a verification finding."""

    __tablename__ = "evidence_references"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_type: Mapped[EvidenceReferenceType] = mapped_column(
        SAEnum(EvidenceReferenceType, native_enum=False), nullable=False
    )
    source_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    excerpt_quote: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    finding: Mapped["VerificationFinding"] = relationship(
        "VerificationFinding", back_populates="evidence_references"
    )
