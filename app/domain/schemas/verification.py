"""Inkloom Sentinel - Verification Schemas.

Request and response DTOs for deterministic brand compliance verification runs,
findings, and evidence references.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import EvidenceReferenceType, FindingCategory, SeverityLevel

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class VerificationRunRequest(BaseModel):
    """Request body for running deterministic verification on a content revision.

    The caller selects the active policy version to run against. Only ACTIVE
    policy versions may be selected; DRAFT, DEPRECATED, and ARCHIVED are rejected.
    """

    policy_id: uuid.UUID = Field(
        ...,
        description="ID of the BrandPolicy (must be ACTIVE) to verify against",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class EvidenceReferenceResponse(BaseModel):
    """Response schema for a single evidence reference."""

    id: uuid.UUID
    finding_id: uuid.UUID
    reference_type: EvidenceReferenceType
    source_identifier: str
    source_url: str | None
    excerpt_quote: str
    confidence_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationFindingResponse(BaseModel):
    """Response schema for a single finding detected during verification."""

    id: uuid.UUID
    run_id: uuid.UUID | None
    revision_id: uuid.UUID
    guideline_id: uuid.UUID | None
    category: FindingCategory
    severity: SeverityLevel
    message: str
    flagged_excerpt: str
    char_start: int | None
    char_end: int | None
    recommendation: str | None
    evidence_references: list[EvidenceReferenceResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationRunResponse(BaseModel):
    """Response schema for a completed verification run."""

    id: uuid.UUID
    revision_id: uuid.UUID
    policy_id: uuid.UUID
    policy_version: int
    status: str
    total_rules: int
    passed_rules: int
    violation_count: int
    inconclusive_count: int
    executed_by_id: str
    execution_time_ms: float
    findings: list[VerificationFindingResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VerificationRunListResponse(BaseModel):
    """Paginated list of verification run summaries."""

    items: list[VerificationRunResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
