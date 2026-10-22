"""Inkloom Sentinel - Evidence & Claim Verification Schemas.

Request and response DTOs for:
- Approved evidence source registry and lifecycle
- Content claims
- Conservative claim assessments with provenance
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.ssrf import validate_safe_url
from app.domain.enums import (
    ClaimAssessmentStatus,
    ClaimDiscoveryStatus,
    ClaimType,
    EvidenceSourceType,
    SourceApprovalStatus,
)

# ---------------------------------------------------------------------------
# Evidence Source Schemas
# ---------------------------------------------------------------------------


class EvidenceSourceCreate(BaseModel):
    """Input schema for creating a new evidence source (starts in DRAFT status)."""

    title: Annotated[
        str, Field(min_length=3, max_length=255, description="Document or source title")
    ]
    source_type: EvidenceSourceType = Field(..., description="Classification of evidence source")
    source_url: Annotated[
        str | None, Field(max_length=1000, description="SSRF-validated web URL")
    ] = None
    internal_reference: Annotated[
        str | None, Field(max_length=255, description="Internal filing or catalog ID")
    ] = None
    publisher_or_owner: Annotated[
        str, Field(min_length=2, max_length=255, description="Publishing organization")
    ]
    effective_date: datetime = Field(..., description="Date when source content becomes effective")
    expiry_date: datetime | None = Field(None, description="Optional expiration date")
    trusted_excerpts: list[str] = Field(
        default_factory=list,
        description="List of authoritative verbatim excerpts or quotes",
    )
    structured_facts: list[dict] = Field(
        default_factory=list,
        description="Structured assertions or facts with keywords, support, and contradiction terms",
    )

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return validate_safe_url(v)

    @field_validator("title", "publisher_or_owner")
    @classmethod
    def strip_and_verify_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be blank.")
        return v.strip()

    @model_validator(mode="after")
    def validate_dates_and_identifiers(self) -> "EvidenceSourceCreate":
        from datetime import UTC

        if not self.source_url and not self.internal_reference:
            raise ValueError(
                "At least one of 'source_url' or 'internal_reference' must be provided."
            )
        if self.expiry_date and self.effective_date:
            exp = self.expiry_date
            eff = self.effective_date
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if eff.tzinfo is None:
                eff = eff.replace(tzinfo=UTC)
            if exp < eff:
                raise ValueError("expiry_date cannot be earlier than effective_date.")
        return self


class EvidenceSourceUpdate(BaseModel):
    """Input schema for updating an existing evidence source."""

    title: Annotated[str | None, Field(min_length=3, max_length=255)] = None
    source_type: EvidenceSourceType | None = None
    source_url: Annotated[str | None, Field(max_length=1000)] = None
    internal_reference: Annotated[str | None, Field(max_length=255)] = None
    publisher_or_owner: Annotated[str | None, Field(min_length=2, max_length=255)] = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    trusted_excerpts: list[str] | None = None
    structured_facts: list[dict] | None = None

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_safe_url(v)
        return v


class EvidenceSourceRejectRequest(BaseModel):
    """Reason required when rejecting an evidence source."""

    reason: Annotated[
        str, Field(min_length=3, max_length=500, description="Justification for rejection")
    ]


class EvidenceSourceRevokeRequest(BaseModel):
    """Reason required when revoking an approved evidence source."""

    reason: Annotated[
        str, Field(min_length=3, max_length=500, description="Justification for revoking source")
    ]


class EvidenceSourceResponse(BaseModel):
    """Output representation of an evidence source."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    source_type: EvidenceSourceType
    source_url: str | None
    internal_reference: str | None
    publisher_or_owner: str
    effective_date: datetime
    expiry_date: datetime | None
    approval_status: SourceApprovalStatus
    version: int
    trusted_excerpts: list[str]
    structured_facts: list[dict]
    created_by_id: str
    approved_by_id: str | None
    approved_at: datetime | None
    rejection_reason: str | None
    is_valid: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvidenceSourceListResponse(BaseModel):
    """Paginated list of evidence sources."""

    items: list[EvidenceSourceResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# ---------------------------------------------------------------------------
# Content Claim Schemas
# ---------------------------------------------------------------------------


class ContentClaimCreate(BaseModel):
    """Input schema for recording a claim against a content revision."""

    claim_text: Annotated[
        str, Field(min_length=3, max_length=2000, description="The substantive statement")
    ]
    claim_type: ClaimType = Field(ClaimType.FACTUAL, description="Classification of the claim")
    context_excerpt: Annotated[str | None, Field(max_length=1000)] = None
    char_start: int | None = Field(None, ge=0)
    char_end: int | None = Field(None, ge=0)

    @field_validator("claim_text")
    @classmethod
    def claim_text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("claim_text must not be blank.")
        return v.strip()


class ClaimAssessmentSnapshot(BaseModel):
    """Summary of a claim assessment for inclusion in claim detail."""

    id: uuid.UUID
    assessment_status: ClaimAssessmentStatus
    explanation: str
    uncertainty_score: float | None
    engine_version: str
    assessed_at: datetime
    supporting_sources_snapshot: list[dict]
    contradicting_sources_snapshot: list[dict]

    model_config = {"from_attributes": True}


class ContentClaimResponse(BaseModel):
    """Output representation of a content claim."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    revision_id: uuid.UUID
    claim_text: str
    claim_type: ClaimType
    context_excerpt: str | None
    char_start: int | None
    char_end: int | None
    discovery_status: ClaimDiscoveryStatus = ClaimDiscoveryStatus.CANDIDATE
    extraction_method: str | None = None
    extraction_version: str | None = None
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    created_by_id: str
    latest_assessment: ClaimAssessmentSnapshot | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentClaimUpdate(BaseModel):
    """Input schema for updating, confirming, dismissing, or reclassifying a claim."""

    claim_text: Annotated[str | None, Field(min_length=3, max_length=2000)] = None
    claim_type: ClaimType | None = None
    discovery_status: ClaimDiscoveryStatus | None = None


class ClaimDiscoveryResponse(BaseModel):
    """Response summary for automated claim discovery."""

    revision_id: uuid.UUID
    discovered_count: int
    existing_count: int
    claims: list[ContentClaimResponse]


class ContentClaimListResponse(BaseModel):
    """Paginated list of content claims."""

    items: list[ContentClaimResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# ---------------------------------------------------------------------------
# Claim Assessment Schemas
# ---------------------------------------------------------------------------


class ClaimAssessmentRequest(BaseModel):
    """Request body for running an evidence assessment on a claim."""

    policy_id: uuid.UUID | None = Field(
        None, description="Optional active BrandPolicy ID to bind against"
    )


class ClaimAssessmentResponse(BaseModel):
    """Output representation of an immutable claim assessment."""

    id: uuid.UUID
    claim_id: uuid.UUID
    revision_id: uuid.UUID
    workspace_id: uuid.UUID
    policy_id: uuid.UUID | None
    policy_version: int | None
    assessment_status: ClaimAssessmentStatus
    explanation: str
    uncertainty_score: float | None
    engine_version: str
    assessed_by_id: str
    assessed_at: datetime
    supporting_sources_snapshot: list[dict]
    contradicting_sources_snapshot: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimAssessmentListResponse(BaseModel):
    """Paginated historical assessments for a claim."""

    items: list[ClaimAssessmentResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
