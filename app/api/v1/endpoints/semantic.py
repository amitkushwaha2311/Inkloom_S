"""Inkloom Sentinel - Semantic Review Endpoints.

Authenticated, workspace-scoped endpoints to:
- Execute contextual semantic guideline reviews on a content revision.
- List historical semantic review runs.
- Retrieve individual semantic run findings with uncertainty indicators.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_semantic_service,
    get_workspace_service,
)
from app.core.config import settings
from app.core.rate_limit import expensive_ops_limiter
from app.domain.enums import WorkspaceRole
from app.domain.models.semantic import SemanticReviewFinding, SemanticReviewRun
from app.domain.schemas.semantic import (
    SemanticReviewFindingResponse,
    SemanticReviewRunListResponse,
    SemanticReviewRunRequest,
    SemanticReviewRunResponse,
)
from app.services.semantic_service import SemanticService
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/submissions/{submission_id}/revisions/{revision_number}/semantic-review/runs",
    tags=["Semantic Review"],
)

_WRITE_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
    WorkspaceRole.CONTRIBUTOR,
}

SemanticSvc = Annotated[SemanticService, Depends(get_semantic_service)]
WsSvc = Annotated[WorkspaceService, Depends(get_workspace_service)]


def _serialize_finding(f: SemanticReviewFinding) -> SemanticReviewFindingResponse:
    return SemanticReviewFindingResponse(
        id=f.id,
        run_id=f.run_id,
        guideline_id=f.guideline_id,
        category=f.category,
        outcome=f.outcome,
        explanation=f.explanation,
        flagged_excerpt=f.flagged_excerpt,
        char_start=f.char_start,
        char_end=f.char_end,
        confidence_score=f.confidence_score,
        uncertainty_reason=f.uncertainty_reason,
        recommendation=f.recommendation,
        created_at=f.created_at,
    )


def _serialize_run(run: SemanticReviewRun) -> SemanticReviewRunResponse:
    findings = []
    if "findings" in run.__dict__ and run.findings:
        findings = [_serialize_finding(f) for f in run.findings]

    return SemanticReviewRunResponse(
        id=run.id,
        revision_id=run.revision_id,
        policy_id=run.policy_id,
        policy_version=run.policy_version,
        status=run.status,
        overall_outcome=run.overall_outcome,
        total_guidelines=run.total_guidelines,
        passed_count=run.passed_count,
        violation_count=run.violation_count,
        needs_review_count=run.needs_review_count,
        inconclusive_count=run.inconclusive_count,
        executed_by_id=run.executed_by_id,
        engine_version=run.engine_version,
        execution_time_ms=run.execution_time_ms,
        findings=findings,
        created_at=run.created_at,
    )


@router.post(
    "",
    response_model=SemanticReviewRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Semantic Review Run",
    description=(
        "Executes a contextual semantic guideline review of a content revision against an ACTIVE brand policy. "
        "Evaluates tone, brand voice, unsubstantiated superlatives, and instruction injection resistance. "
        "Requires CONTRIBUTOR or above. Preserves historical immutability."
    ),
)
async def run_semantic_review(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    body: SemanticReviewRunRequest,
    current_user: CurrentUser,
    svc: SemanticSvc,
    ws_svc: WsSvc,
) -> SemanticReviewRunResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    if settings.RATE_LIMIT_ENABLED:
        await expensive_ops_limiter.check_rate_limit(
            key=f"expensive:{current_user.id}",
            max_requests=settings.VERIFY_RATE_LIMIT_MAX_REQUESTS,
        )
    run = await svc.run_semantic_review(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        policy_id=body.policy_id,
        actor_id=str(current_user.id),
    )
    return _serialize_run(run)


@router.get(
    "",
    response_model=SemanticReviewRunListResponse,
    summary="List Semantic Review Runs",
    description="Lists historical semantic review runs for a revision. Requires active workspace membership.",
)
async def list_semantic_runs(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: SemanticSvc,
    ws_svc: WsSvc,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SemanticReviewRunListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    runs, total = await svc.list_runs(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        page=page,
        page_size=page_size,
    )
    return SemanticReviewRunListResponse(
        items=[_serialize_run(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/{run_id}",
    response_model=SemanticReviewRunResponse,
    summary="Get Semantic Review Run",
    description="Retrieves a specific semantic review run by ID. Requires active workspace membership.",
)
async def get_semantic_run(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    run_id: uuid.UUID,
    current_user: CurrentUser,
    svc: SemanticSvc,
    ws_svc: WsSvc,
) -> SemanticReviewRunResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    run = await svc.get_run(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        run_id=run_id,
    )
    return _serialize_run(run)
