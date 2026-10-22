"""Inkloom Sentinel - Deterministic Verification Endpoints.

Routes for running brand compliance verification, retrieving runs, and listing
run history — all workspace-scoped and JWT-authenticated.

Authorization:
  - All endpoints require a valid Bearer JWT.
  - Actor identity is resolved from the verified JWT — never from a client header.
  - Workspace membership is enforced via WorkspaceService before every operation.
  - Running verification requires CONTRIBUTOR role or above.
  - Reading run history and results requires any active workspace membership.
  - Cross-workspace access returns 404 to prevent resource enumeration.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_verification_service,
    get_workspace_service,
)
from app.core.config import settings
from app.core.rate_limit import expensive_ops_limiter
from app.domain.enums import WorkspaceRole
from app.domain.schemas.verification import (
    VerificationRunListResponse,
    VerificationRunRequest,
    VerificationRunResponse,
)
from app.services.verification_service import VerificationService
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/submissions/{submission_id}/verification",
    tags=["Verification"],
)

# Roles that may trigger a new verification run
_VERIFY_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
    WorkspaceRole.CONTRIBUTOR,
}

# Convenience annotated aliases for DI
VerifySvc = Annotated[VerificationService, Depends(get_verification_service)]
WsSvc = Annotated[WorkspaceService, Depends(get_workspace_service)]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_run(run) -> VerificationRunResponse:
    return VerificationRunResponse.model_validate(run)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/runs",
    response_model=VerificationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Deterministic Verification",
    description=(
        "Run deterministic brand compliance verification on a specific content revision "
        "against an explicitly selected ACTIVE BrandPolicy. "
        "Pass the target revision_number as a query parameter. "
        "Requires CONTRIBUTOR role or above. "
        "The selected policy must be ACTIVE; DRAFT, DEPRECATED, and ARCHIVED policies "
        "are rejected with a 422 validation error. "
        "Returns the full VerificationRun including all findings and evidence references."
    ),
)
async def run_verification(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    body: VerificationRunRequest,
    current_user: CurrentUser,
    svc: VerifySvc,
    ws_svc: WsSvc,
    revision_number: int = Query(..., ge=1, description="Revision number to verify"),
) -> VerificationRunResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_VERIFY_ROLES
    )
    if settings.RATE_LIMIT_ENABLED:
        await expensive_ops_limiter.check_rate_limit(
            key=f"verify:{current_user.id}",
            max_requests=settings.VERIFY_RATE_LIMIT_MAX_REQUESTS,
        )
    run = await svc.run_verification(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        policy_id=body.policy_id,
        actor_id=str(current_user.id),
    )
    return _serialize_run(run)


@router.get(
    "/runs",
    response_model=VerificationRunListResponse,
    summary="List Verification Runs",
    description=(
        "List historical verification runs for a content submission. "
        "Optionally filter to runs against a specific revision number. "
        "Requires any active workspace membership."
    ),
)
async def list_verification_runs(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    current_user: CurrentUser,
    svc: VerifySvc,
    ws_svc: WsSvc,
    revision_number: Annotated[
        int | None, Query(ge=1, description="Filter runs to a specific revision")
    ] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> VerificationRunListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items, total = await svc.list_runs(
        submission_id=submission_id,
        workspace_id=workspace_id,
        revision_number=revision_number,
        page=page,
        page_size=page_size,
    )
    return VerificationRunListResponse(
        items=[_serialize_run(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/runs/{run_id}",
    response_model=VerificationRunResponse,
    summary="Get Verification Run",
    description=(
        "Retrieve a single verification run with all its findings and evidence references. "
        "Requires any active workspace membership."
    ),
)
async def get_verification_run(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: CurrentUser,
    svc: VerifySvc,
    ws_svc: WsSvc,
) -> VerificationRunResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    run = await svc.get_run(
        run_id=run_id,
        submission_id=submission_id,
        workspace_id=workspace_id,
    )
    return _serialize_run(run)
