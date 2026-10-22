"""Inkloom Sentinel - Semantic Review Schemas.

Request and response DTOs for:
- Semantic guideline evaluations
- Semantic review runs and findings
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import FindingCategory, SemanticOutcome


class SemanticReviewRunRequest(BaseModel):
    """Request body for running a semantic review of a revision against an ACTIVE policy."""

    policy_id: uuid.UUID = Field(
        ...,
        description="ID of the BrandPolicy (must be ACTIVE) to evaluate against",
    )


class SemanticReviewFindingResponse(BaseModel):
    """Response schema for an individual semantic review finding."""

    id: uuid.UUID
    run_id: uuid.UUID
    guideline_id: uuid.UUID | None
    category: FindingCategory
    outcome: SemanticOutcome
    explanation: str
    flagged_excerpt: str | None
    char_start: int | None
    char_end: int | None
    confidence_score: float | None
    uncertainty_reason: str | None
    recommendation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SemanticReviewRunResponse(BaseModel):
    """Response schema for a completed semantic review run."""

    id: uuid.UUID
    revision_id: uuid.UUID
    policy_id: uuid.UUID
    policy_version: int
    status: str
    overall_outcome: SemanticOutcome
    total_guidelines: int
    passed_count: int
    violation_count: int
    needs_review_count: int
    inconclusive_count: int
    executed_by_id: str
    engine_version: str
    execution_time_ms: float
    findings: list[SemanticReviewFindingResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class SemanticReviewRunListResponse(BaseModel):
    """Paginated list of semantic review runs."""

    items: list[SemanticReviewRunResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
