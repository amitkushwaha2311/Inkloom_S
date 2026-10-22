"""Inkloom Sentinel - Brand Policy Management Endpoints.

Routes for policy CRUD, version management, lifecycle transitions,
and guideline ingestion within brand workspaces.

Authorization:
  - All endpoints require a valid JWT (Bearer token).
  - Actor identity is resolved from the verified JWT — never from a header.
  - Workspace membership is enforced before every operation via WorkspaceService.
  - Write operations require OWNER or ADMIN role (see per-endpoint docstrings).
  - Read operations require any active membership.
  - Cross-workspace access returns 404 (not 403) to avoid resource enumeration.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_policy_service,
    get_workspace_service,
)
from app.core.errors import ValidationError
from app.domain.enums import PolicyStatus, WorkspaceRole
from app.domain.schemas.policy import (
    GuidelineCreate,
    GuidelineResponse,
    GuidelineUpdate,
    PolicyActivateRequest,
    PolicyCreate,
    PolicyDeprecateRequest,
    PolicyDetailResponse,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
    PolicyVersionHistoryItem,
    PolicyVersionHistoryResponse,
)
from app.services.policy_service import PolicyService
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/policies",
    tags=["Brand Policy Management"],
)

# Roles that can write policies / guidelines
_WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}


def _policy_to_response(policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        workspace_id=policy.workspace_id,
        name=policy.name,
        description=policy.description,
        version=policy.version,
        status=policy.status,
        created_by_id=policy.created_by_id,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        guideline_count=len(policy.guidelines),
    )


def _policy_to_detail(policy) -> PolicyDetailResponse:
    return PolicyDetailResponse(
        id=policy.id,
        workspace_id=policy.workspace_id,
        name=policy.name,
        description=policy.description,
        version=policy.version,
        status=policy.status,
        created_by_id=policy.created_by_id,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        guideline_count=len(policy.guidelines),
        guidelines=[GuidelineResponse.model_validate(g) for g in policy.guidelines],
    )


# ---------------------------------------------------------------------------
# Policy CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=PolicyDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Brand Policy",
    description=(
        "Creates a new brand policy in DRAFT status at version 1. "
        "Requires OWNER or ADMIN workspace role."
    ),
)
async def create_policy(
    workspace_id: uuid.UUID,
    body: PolicyCreate,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    policy = await svc.create_policy(workspace_id, body, str(current_user.id))
    return _policy_to_detail(policy)


@router.get(
    "",
    response_model=PolicyListResponse,
    summary="List Brand Policies",
    description="Returns a paginated list of policies. Requires active membership.",
)
async def list_policies(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    status_filter: PolicyStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items, total = await svc.list_policies(
        workspace_id, status=status_filter, page=page, page_size=page_size
    )
    return PolicyListResponse(
        items=[_policy_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyDetailResponse,
    summary="Get Policy Detail",
    description="Returns a single policy with all its guidelines. Requires membership.",
)
async def get_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    policy = await svc.get_policy(workspace_id, policy_id)
    return _policy_to_detail(policy)


@router.patch(
    "/{policy_id}",
    response_model=PolicyDetailResponse,
    summary="Update DRAFT Policy Metadata",
    description="Updates the name or description of a DRAFT policy. Requires OWNER or ADMIN.",
)
async def update_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    policy = await svc.update_policy_metadata(workspace_id, policy_id, body, str(current_user.id))
    return _policy_to_detail(policy)


# ---------------------------------------------------------------------------
# Version history and forking
# ---------------------------------------------------------------------------


@router.get(
    "/history/{policy_name}",
    response_model=PolicyVersionHistoryResponse,
    summary="Get Policy Version History",
)
async def get_version_history(
    workspace_id: uuid.UUID,
    policy_name: str,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyVersionHistoryResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    versions = await svc.get_version_history(workspace_id, policy_name)
    return PolicyVersionHistoryResponse(
        workspace_id=workspace_id,
        policy_name=policy_name,
        versions=[
            PolicyVersionHistoryItem(
                id=v.id,
                version=v.version,
                status=v.status,
                created_by_id=v.created_by_id,
                created_at=v.created_at,
                updated_at=v.updated_at,
                guideline_count=len(v.guidelines),
            )
            for v in versions
        ],
    )


@router.post(
    "/{policy_id}/versions",
    response_model=PolicyDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Fork New Policy Version",
    description="Creates a new DRAFT version from an ACTIVE policy. Requires OWNER or ADMIN.",
)
async def fork_new_version(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    policy = await svc.create_new_version(workspace_id, policy_id, str(current_user.id))
    return _policy_to_detail(policy)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{policy_id}/activate",
    response_model=PolicyDetailResponse,
    summary="Activate DRAFT Policy",
    description="Transitions a DRAFT policy to ACTIVE. Requires OWNER or ADMIN.",
)
async def activate_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: PolicyActivateRequest,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    if not body.confirm:
        raise ValidationError("confirm must be true to activate a policy")
    policy = await svc.activate_policy(workspace_id, policy_id, str(current_user.id))
    return _policy_to_detail(policy)


@router.post(
    "/{policy_id}/deprecate",
    response_model=PolicyDetailResponse,
    summary="Deprecate Active Policy",
    description="Transitions an ACTIVE policy to DEPRECATED. Requires OWNER or ADMIN.",
)
async def deprecate_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: PolicyDeprecateRequest,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    policy = await svc.deprecate_policy(workspace_id, policy_id, str(current_user.id), body.reason)
    return _policy_to_detail(policy)


@router.post(
    "/{policy_id}/archive",
    response_model=PolicyDetailResponse,
    summary="Archive Policy (Terminal)",
    description="Transitions a policy to ARCHIVED. Requires OWNER or ADMIN.",
)
async def archive_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> PolicyDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    policy = await svc.archive_policy(workspace_id, policy_id, str(current_user.id))
    return _policy_to_detail(policy)


# ---------------------------------------------------------------------------
# Guideline management
# ---------------------------------------------------------------------------


@router.post(
    "/{policy_id}/guidelines",
    response_model=GuidelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Guideline to DRAFT Policy",
    description="Adds a validated guideline to a DRAFT policy. Requires OWNER or ADMIN.",
)
async def add_guideline(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: GuidelineCreate,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> GuidelineResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    guideline = await svc.add_guideline(workspace_id, policy_id, body, str(current_user.id))
    return GuidelineResponse.model_validate(guideline)


@router.get(
    "/{policy_id}/guidelines",
    response_model=list[GuidelineResponse],
    summary="List Policy Guidelines",
    description="Returns all guidelines for a policy. Requires membership.",
)
async def list_guidelines(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> list[GuidelineResponse]:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    guidelines = await svc.list_guidelines(workspace_id, policy_id)
    return [GuidelineResponse.model_validate(g) for g in guidelines]


@router.patch(
    "/{policy_id}/guidelines/{guideline_id}",
    response_model=GuidelineResponse,
    summary="Update Guideline",
    description="Updates fields on a guideline. Policy must be DRAFT. Requires OWNER or ADMIN.",
)
async def update_guideline(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    guideline_id: uuid.UUID,
    body: GuidelineUpdate,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> GuidelineResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    guideline = await svc.update_guideline(
        workspace_id, policy_id, guideline_id, body, str(current_user.id)
    )
    return GuidelineResponse.model_validate(guideline)


@router.delete(
    "/{policy_id}/guidelines/{guideline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Guideline from DRAFT Policy",
    description="Removes a guideline from a DRAFT policy. Requires OWNER or ADMIN.",
)
async def delete_guideline(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    guideline_id: uuid.UUID,
    current_user: CurrentUser,
    svc: PolicyService = Depends(get_policy_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> None:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    await svc.delete_guideline(workspace_id, policy_id, guideline_id, str(current_user.id))
