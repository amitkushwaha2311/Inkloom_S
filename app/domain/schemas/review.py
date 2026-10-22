"""Inkloom Sentinel - Review, Corrections, and Unified Summary Schemas.

Request and response DTOs for:
- Structured correction suggestions and applications
- Formal human review determinations
- Unified compliance review summary orchestration
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import (
    CorrectionStatus,
    ReviewDecisionType,
    UnifiedCheckStatus,
    UnifiedReviewOutcome,
)


class CorrectionSuggestionCreate(BaseModel):
    """Input schema for creating a structured correction suggestion."""

    original_text: Annotated[
        str,
        Field(
            min_length=1, max_length=2000, description="The original text flagged for correction"
        ),
    ]
    char_start: int | None = Field(None, ge=0)
    char_end: int | None = Field(None, ge=0)
    proposed_replacement: Annotated[str | None, Field(max_length=2000)] = None
    recommended_action: Annotated[
        str, Field(min_length=3, max_length=1000, description="Recommended remediation action")
    ]
    reason: Annotated[
        str, Field(min_length=3, max_length=1000, description="Rationale for this correction")
    ]
    finding_id: uuid.UUID | None = None
    guideline_id: uuid.UUID | None = None
    evidence_source_id: uuid.UUID | None = None
    evidence_excerpt: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("original_text", "recommended_action", "reason")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank.")
        return v.strip()


class CorrectionSuggestionUpdate(BaseModel):
    """Input schema for updating suggestion status or details."""

    status: CorrectionStatus | None = None
    proposed_replacement: Annotated[str | None, Field(max_length=2000)] = None
    recommended_action: Annotated[str | None, Field(min_length=3, max_length=1000)] = None
    reason: Annotated[str | None, Field(min_length=3, max_length=1000)] = None


class CorrectionSuggestionResponse(BaseModel):
    """Output representation of a correction suggestion."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    submission_id: uuid.UUID
    revision_id: uuid.UUID
    finding_id: uuid.UUID | None
    guideline_id: uuid.UUID | None
    original_text: str
    char_start: int | None
    char_end: int | None
    proposed_replacement: str | None
    recommended_action: str
    reason: str
    evidence_source_id: uuid.UUID | None
    evidence_excerpt: str | None
    status: CorrectionStatus
    created_by_id: str
    reviewed_by_id: str | None
    applied_revision_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CorrectionSuggestionListResponse(BaseModel):
    """List of correction suggestions."""

    items: list[CorrectionSuggestionResponse]
    total: int


class ApplyCorrectionRequest(BaseModel):
    """Request schema for applying an accepted correction as a new revision."""

    expected_revision_number: int = Field(
        ...,
        description="Concurrency guard: must match the revision number being modified",
        ge=1,
    )


class ApplyCorrectionResponse(BaseModel):
    """Response returned upon successfully creating a new revision from an applied correction."""

    suggestion_id: uuid.UUID
    new_revision_id: uuid.UUID
    new_revision_number: int
    content_text: str
    change_summary: str


class ReviewDecisionCreate(BaseModel):
    """Input schema for recording an explicit human review decision."""

    decision: ReviewDecisionType
    rationale_summary: Annotated[
        str,
        Field(min_length=3, max_length=2000, description="Justification for the review decision"),
    ]
    feedback_notes: Annotated[str | None, Field(max_length=5000)] = None
    policy_id: uuid.UUID | None = None
    policy_version: int | None = None
    review_run_id: uuid.UUID | None = None

    @field_validator("rationale_summary")
    @classmethod
    def rationale_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rationale_summary must not be blank.")
        return v.strip()


class ReviewDecisionResponse(BaseModel):
    """Output representation of a review decision."""

    id: uuid.UUID
    submission_id: uuid.UUID
    revision_id: uuid.UUID
    reviewer_id: str
    decision: ReviewDecisionType
    rationale_summary: str
    feedback_notes: str | None
    policy_id: uuid.UUID | None
    policy_version: int | None
    review_run_id: uuid.UUID | None
    decided_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecisionListResponse(BaseModel):
    """List of review decisions."""

    items: list[ReviewDecisionResponse]
    total: int


# ---------------------------------------------------------------------------
# Unified Review Orchestration Schemas
# ---------------------------------------------------------------------------


class CheckExecutionSummary(BaseModel):
    """Execution status and summary metrics for an individual verification component."""

    name: str
    status: UnifiedCheckStatus
    outcome: str | None = None
    run_id: uuid.UUID | None = None
    engine_version: str | None = None
    execution_timestamp: datetime | None = None
    finding_count: int = 0
    message: str | None = None


class UnifiedReviewSummaryResponse(BaseModel):
    """Synthesized orchestration summary for a ContentRevision and BrandPolicy version."""

    revision_id: uuid.UUID
    revision_number: int
    submission_id: uuid.UUID
    workspace_id: uuid.UUID
    policy_id: uuid.UUID
    policy_version: int
    policy_name: str
    overall_outcome: UnifiedReviewOutcome
    is_clean_pass: bool = Field(
        ...,
        description="True ONLY if all required checks ran, completed, and returned PASS without unresolved issues",
    )
    checks: dict[str, CheckExecutionSummary]
    deterministic_findings: list[dict] = Field(default_factory=list)
    claim_assessments: list[dict] = Field(default_factory=list)
    semantic_findings: list[dict] = Field(default_factory=list)
    correction_suggestions: list[CorrectionSuggestionResponse] = Field(default_factory=list)
    review_decisions: list[ReviewDecisionResponse] = Field(default_factory=list)
    unresolved_issues_count: int = 0
    generated_at: datetime
