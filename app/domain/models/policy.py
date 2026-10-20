"""Inkloom Sentinel - Versioned Policies & Approved Guidelines Models.

Domain entities representing brand governance rulebooks, versioning,
and categorized rule clauses with positive and negative examples.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
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

from app.domain.enums import FindingCategory, PolicyStatus, SeverityLevel
from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.models.workspace import BrandWorkspace


class BrandPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A versioned set of brand governance rules and compliance criteria."""

    __tablename__ = "brand_policies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", "version", name="uq_workspace_policy_version"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        SAEnum(PolicyStatus, native_enum=False), default=PolicyStatus.DRAFT, nullable=False
    )
    created_by_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    workspace: Mapped["BrandWorkspace"] = relationship("BrandWorkspace", back_populates="policies")
    guidelines: Mapped[list["PolicyGuideline"]] = relationship(
        "PolicyGuideline", back_populates="policy", cascade="all, delete-orphan", lazy="selectin"
    )


class PolicyGuideline(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An individual verifiable rule clause under a brand policy."""

    __tablename__ = "policy_guidelines"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(
        SAEnum(FindingCategory, native_enum=False), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    examples_approved: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    examples_prohibited: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    severity_default: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel, native_enum=False), default=SeverityLevel.MEDIUM, nullable=False
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    policy: Mapped["BrandPolicy"] = relationship("BrandPolicy", back_populates="guidelines")
