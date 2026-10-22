"""Inkloom Sentinel - Audit Trail & Governance Analytics Schemas.

Pydantic schemas governing:
- Workspace audit timeline listing, pagination, and related entity references.
- Full provenance and review history across revisions, policy versions, and decisions.
- Governance analytics metrics including violations, turnaround times, and acceptance rates.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import (
    AuditEventType,
    FindingCategory,
    SeverityLevel,
    SubmissionStatus,
)

# ---------------------------------------------------------------------------
# Workspace Audit Timeline Schemas
# ---------------------------------------------------------------------------


class AuditRelatedEntity(BaseModel):
    """Contextual reference to a domain entity associated with an audit event."""

    resource_type: str = Field(..., description="Target entity type, e.g. ContentSubmission")
    resource_id: str = Field(..., description="Unique entity identifier")
    display_name: str | None = Field(
        None, description="Human-readable title or label if entity exists"
    )
    is_available: bool = Field(
        True,
        description="False if the entity has been deleted, archived, or is unavailable",
    )
    details: dict[str, Any] | None = Field(None, description="Safe summary metadata for the entity")


class AuditEventResponse(BaseModel):
    """An immutable, append-only domain audit record with resolved references."""

    id: uuid.UUID
    workspace_id: uuid.UUID | None
    event_type: AuditEventType
    actor_id: str
    resource_type: str
    resource_id: str
    event_payload: dict[str, Any]
    ip_address_hash: str | None = None
    user_agent_snippet: str | None = None
    occurred_at: datetime
    related_entity: AuditRelatedEntity | None = None

    model_config = {"from_attributes": True}


class AuditEventListResponse(BaseModel):
    """Paginated collection of workspace audit events."""

    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# ---------------------------------------------------------------------------
# Submission Provenance & Review History Schemas
# ---------------------------------------------------------------------------


class VerificationFindingProvenance(BaseModel):
    """Snapshot of a deterministic verification finding."""

    id: uuid.UUID
    guideline_id: uuid.UUID | None = None
    category: FindingCategory
    severity: SeverityLevel
    message: str
    flagged_excerpt: str
    char_start: int | None = None
    char_end: int | None = None
    recommendation: str | None = None
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)


class DeterministicProvenance(BaseModel):
    """Deterministic verification lifecycle state for a revision."""

    status: str = Field(
        ...,
        description="verified_clean, violations_found, or not_run (missing historical verification)",
    )
    run_id: uuid.UUID | None = None
    policy_id: uuid.UUID | None = None
    policy_version: int | None = None
    total_rules: int = 0
    passed_rules: int = 0
    violation_count: int = 0
    executed_by_id: str | None = None
    executed_at: datetime | None = None
    findings: list[VerificationFindingProvenance] = Field(default_factory=list)


class ClaimAssessmentProvenance(BaseModel):
    """Claim and evidence assessment provenance."""

    claim_id: uuid.UUID
    claim_text: str
    claim_type: str
    discovery_status: str
    char_start: int | None = None
    char_end: int | None = None
    assessment_status: str | None = None
    explanation: str | None = None
    uncertainty_score: float | None = None
    supporting_sources: list[dict[str, Any]] = Field(default_factory=list)
    contradicting_sources: list[dict[str, Any]] = Field(default_factory=list)


class ClaimsProvenance(BaseModel):
    """Claims extraction and assessment lifecycle state for a revision."""

    status: str = Field(
        ...,
        description="assessed, no_claims_discovered, or not_assessed (missing historical assessment)",
    )
    total_claims: int = 0
    claims: list[ClaimAssessmentProvenance] = Field(default_factory=list)


class SemanticFindingProvenance(BaseModel):
    """Snapshot of a semantic review finding."""

    id: uuid.UUID
    guideline_id: uuid.UUID | None = None
    category: FindingCategory
    outcome: str
    explanation: str
    flagged_excerpt: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    confidence_score: float | None = None
    uncertainty_reason: str | None = None
    recommendation: str | None = None


class SemanticReviewProvenance(BaseModel):
    """Semantic review lifecycle state for a revision."""

    status: str = Field(
        ...,
        description="verified_clean, issues_flagged, or not_run (missing historical review)",
    )
    run_id: uuid.UUID | None = None
    policy_id: uuid.UUID | None = None
    policy_version: int | None = None
    overall_outcome: str | None = None
    violation_count: int = 0
    needs_review_count: int = 0
    engine_version: str | None = None
    executed_at: datetime | None = None
    findings: list[SemanticFindingProvenance] = Field(default_factory=list)


class CorrectionSuggestionProvenance(BaseModel):
    """Correction suggestion linked to a revision."""

    id: uuid.UUID
    original_text: str
    proposed_replacement: str | None = None
    recommended_action: str
    reason: str
    status: str
    created_by_id: str
    reviewed_by_id: str | None = None
    applied_revision_id: uuid.UUID | None = None
    created_at: datetime


class ReviewDecisionProvenance(BaseModel):
    """Formal human review determination rendered on a revision."""

    id: uuid.UUID
    decision: str
    reviewer_id: str
    rationale_summary: str
    feedback_notes: str | None = None
    policy_id: uuid.UUID | None = None
    policy_version: int | None = None
    decided_at: datetime


class RevisionProvenanceItem(BaseModel):
    """Comprehensive lifecycle provenance for an individual content revision."""

    revision_id: uuid.UUID
    revision_number: int
    content_format: str
    content_hash: str | None = None
    content_length: int = 0
    change_summary: str | None = None
    source_metadata: dict[str, Any] | None = None
    submitted_at: datetime
    created_by_id: str | None = None
    was_applied_from_suggestion_id: uuid.UUID | None = None
    deterministic_verification: DeterministicProvenance
    claims_verification: ClaimsProvenance
    semantic_review: SemanticReviewProvenance
    correction_suggestions: list[CorrectionSuggestionProvenance] = Field(default_factory=list)
    review_decisions: list[ReviewDecisionProvenance] = Field(default_factory=list)


class SubmissionProvenanceResponse(BaseModel):
    """Full lifecycle provenance and audit history for a content submission."""

    submission_id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    campaign_tag: str | None = None
    current_status: SubmissionStatus
    author_id: str
    created_at: datetime
    updated_at: datetime
    total_revisions: int
    revisions: list[RevisionProvenanceItem]
    lifecycle_summary: dict[str, Any] = Field(
        ...,
        description="Summary of policies used, total decisions rendered, and governance outcome",
    )


# ---------------------------------------------------------------------------
# Governance Analytics Schemas
# ---------------------------------------------------------------------------


class CategoryViolationMetric(BaseModel):
    """Aggregation of flagged violations by guideline category."""

    category: FindingCategory
    count: int = Field(..., ge=0, description="Total violations flagged in this category")


class SeverityViolationMetric(BaseModel):
    """Aggregation of deterministic findings by severity level."""

    severity: SeverityLevel
    count: int = Field(..., ge=0, description="Total findings flagged at this severity level")


class GuidelineViolationMetric(BaseModel):
    """Most frequent guideline violation ranking."""

    guideline_id: uuid.UUID | None = None
    guideline_title: str | None = None
    category: str
    violation_count: int = Field(..., ge=0)


class HumanInterventionMetric(BaseModel):
    """Quantifies human reviewer intervention rates on content."""

    total_reviews_completed: int = Field(..., ge=0)
    reviews_requiring_intervention: int = Field(
        ...,
        ge=0,
        description="Decisions requiring human intervention (REQUEST_CHANGES or REJECT)",
    )
    intervention_rate_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of completed reviews requiring human intervention (0.0 if denominator is 0)",
    )
    definition: str = "Percentage of formal review decisions requiring human action (changes requested or rejected)"


class CorrectionAcceptanceMetric(BaseModel):
    """Quantifies suggestion acceptance rate by creators."""

    total_suggestions: int = Field(..., ge=0)
    accepted_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)
    proposed_count: int = Field(..., ge=0)
    acceptance_rate_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Accepted suggestions / total suggestions * 100.0 (0.0 if denominator is 0)",
    )
    definition: str = "Percentage of structured correction suggestions accepted into new revisions"


class TurnaroundTimeMetric(BaseModel):
    """Review turnaround duration measured from revision submission to review decision."""

    total_decisions_measured: int = Field(..., ge=0)
    average_hours: float | None = Field(
        None,
        description="Mean hours between revision submission and decision (None if no decisions)",
    )
    median_hours: float | None = Field(
        None,
        description="Median hours between revision submission and decision (None if no decisions)",
    )
    min_hours: float | None = Field(None)
    max_hours: float | None = Field(None)
    definition: str = "Duration in hours elapsed between ContentRevision.submitted_at and ReviewDecision.decided_at"


class TimelineTrendPoint(BaseModel):
    """Time-series metric point for historical trend analysis."""

    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    submissions_count: int = Field(0, ge=0)
    revisions_count: int = Field(0, ge=0)
    reviews_completed: int = Field(0, ge=0)
    violations_flagged: int = Field(0, ge=0)


class GovernanceAnalyticsResponse(BaseModel):
    """Workspace-scoped governance and brand compliance analytics report."""

    workspace_id: uuid.UUID
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    total_submissions: int = Field(..., ge=0)
    total_revisions: int = Field(..., ge=0)
    total_reviews_completed: int = Field(..., ge=0)
    violations_by_category: list[CategoryViolationMetric]
    violations_by_severity: list[SeverityViolationMetric]
    most_frequent_guideline_violations: list[GuidelineViolationMetric]
    human_intervention: HumanInterventionMetric
    correction_acceptance: CorrectionAcceptanceMetric
    turnaround_time: TurnaroundTimeMetric
    historical_trends: list[TimelineTrendPoint]
    generated_at: datetime
