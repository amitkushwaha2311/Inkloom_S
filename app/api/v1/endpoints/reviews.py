"""Inkloom Sentinel - Review Orchestration, Corrections, & Governance Endpoints.

Authenticated, workspace-scoped endpoints to:
- Retrieve unified review summaries across deterministic, evidence, and semantic checks.
- Create, list, update, and apply structured correction suggestions.
- Render formal governance review determinations with separation of duties enforcement.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_review_service,
    get_workspace_service,
)
from app.core.config import settings
from app.core.rate_limit import expensive_ops_limiter
from app.domain.enums import WorkspaceRole
from app.domain.models.review import CorrectionSuggestion, ReviewDecision
from app.domain.schemas.review import (
    ApplyCorrectionRequest,
    ApplyCorrectionResponse,
    CorrectionSuggestionCreate,
    CorrectionSuggestionListResponse,
    CorrectionSuggestionResponse,
    CorrectionSuggestionUpdate,
    ReviewDecisionCreate,
    ReviewDecisionListResponse,
    ReviewDecisionResponse,
    UnifiedReviewSummaryResponse,
)
from app.services.review_service import ReviewService
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/submissions/{submission_id}/revisions/{revision_number}",
    tags=["Unified Review & Governance"],
)

_WRITE_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
    WorkspaceRole.CONTRIBUTOR,
}

_REVIEWER_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
}

ReviewSvc = Annotated[ReviewService, Depends(get_review_service)]
WsSvc = Annotated[WorkspaceService, Depends(get_workspace_service)]


def _serialize_suggestion(s: CorrectionSuggestion) -> CorrectionSuggestionResponse:
    return CorrectionSuggestionResponse.model_validate(s)


def _serialize_decision(d: ReviewDecision) -> ReviewDecisionResponse:
    return ReviewDecisionResponse.model_validate(d)


# ---------------------------------------------------------------------------
# 1. Unified Review Orchestration Summary
# ---------------------------------------------------------------------------


@router.get(
    "/review-summary",
    response_model=UnifiedReviewSummaryResponse,
    summary="Get Unified Review Summary",
    description=(
        "Assembles deterministic findings, evidence claim assessments, and semantic review findings "
        "for one exact ContentRevision and explicitly selected active BrandPolicy version. "
        "Never reports a clean pass when required checks are missing, failed, or unresolved."
    ),
)
async def get_unified_review_summary(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    policy_id: Annotated[
        uuid.UUID, Query(description="ID of the active BrandPolicy version to evaluate against")
    ],
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> UnifiedReviewSummaryResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    if settings.RATE_LIMIT_ENABLED:
        await expensive_ops_limiter.check_rate_limit(
            key=f"expensive:{current_user.id}",
            max_requests=settings.VERIFY_RATE_LIMIT_MAX_REQUESTS,
        )
    return await svc.get_unified_review_summary(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        policy_id=policy_id,
    )


# ---------------------------------------------------------------------------
# 2. Correction Suggestions
# ---------------------------------------------------------------------------


@router.post(
    "/suggestions",
    response_model=CorrectionSuggestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Correction Suggestion",
    description="Creates a structured correction suggestion associated with a finding or guideline.",
)
async def create_correction_suggestion(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    body: CorrectionSuggestionCreate,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> CorrectionSuggestionResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    sugg = await svc.create_correction_suggestion(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        body=body,
        actor_id=str(current_user.id),
    )
    return _serialize_suggestion(sugg)


@router.get(
    "/suggestions",
    response_model=CorrectionSuggestionListResponse,
    summary="List Correction Suggestions",
    description="Lists all structured correction suggestions for a content revision.",
)
async def list_correction_suggestions(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> CorrectionSuggestionListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items = await svc.list_correction_suggestions(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
    )
    return CorrectionSuggestionListResponse(
        items=[_serialize_suggestion(s) for s in items],
        total=len(items),
    )


@router.get(
    "/suggestions/{suggestion_id}",
    response_model=CorrectionSuggestionResponse,
    summary="Get Correction Suggestion",
    description="Retrieves a single correction suggestion by ID.",
)
async def get_correction_suggestion(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    suggestion_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> CorrectionSuggestionResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    sugg = await svc.get_correction_suggestion(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        suggestion_id=suggestion_id,
    )
    return _serialize_suggestion(sugg)


@router.patch(
    "/suggestions/{suggestion_id}",
    response_model=CorrectionSuggestionResponse,
    summary="Update Correction Suggestion",
    description="Updates status (e.g. accepted, rejected) or details of a correction suggestion.",
)
async def update_correction_suggestion(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    suggestion_id: uuid.UUID,
    body: CorrectionSuggestionUpdate,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> CorrectionSuggestionResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    sugg = await svc.update_correction_suggestion(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        suggestion_id=suggestion_id,
        body=body,
        actor_id=str(current_user.id),
    )
    return _serialize_suggestion(sugg)


@router.post(
    "/suggestions/{suggestion_id}/apply",
    response_model=ApplyCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply Correction Suggestion",
    description=(
        "Applies an accepted correction suggestion by creating a brand-new ContentRevision "
        "through the revision service with concurrency protection. Never mutates prior revisions."
    ),
)
async def apply_correction_suggestion(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    suggestion_id: uuid.UUID,
    body: ApplyCorrectionRequest,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> ApplyCorrectionResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    sugg, new_rev = await svc.apply_correction_suggestion(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        suggestion_id=suggestion_id,
        expected_revision_number=body.expected_revision_number,
        actor_id=str(current_user.id),
    )
    change_summary = (new_rev.metadata_payload or {}).get("change_summary", "")
    return ApplyCorrectionResponse(
        suggestion_id=sugg.id,
        new_revision_id=new_rev.id,
        new_revision_number=new_rev.revision_number,
        content_text=new_rev.content_text,
        change_summary=change_summary,
    )


# ---------------------------------------------------------------------------
# 3. Governance Review Decisions
# ---------------------------------------------------------------------------


@router.post(
    "/decisions",
    response_model=ReviewDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Review Decision",
    description=(
        "Records an explicit human review determination (approve, reject, request_changes). "
        "Requires REVIEWER, ADMIN, or OWNER role. Enforces separation of duties (authors cannot self-approve)."
    ),
)
async def record_review_decision(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    body: ReviewDecisionCreate,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> ReviewDecisionResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_REVIEWER_ROLES
    )
    decision = await svc.record_review_decision(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        body=body,
        actor_id=str(current_user.id),
    )
    return _serialize_decision(decision)


@router.get(
    "/decisions",
    response_model=ReviewDecisionListResponse,
    summary="List Review Decisions",
    description="Lists historical human review determinations recorded for a content revision.",
)
async def list_review_decisions(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: ReviewSvc,
    ws_svc: WsSvc,
) -> ReviewDecisionListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    decisions = await svc.list_review_decisions(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
    )
    return ReviewDecisionListResponse(
        items=[_serialize_decision(d) for d in decisions],
        total=len(decisions),
    )
