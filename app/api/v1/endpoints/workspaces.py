"""Inkloom Sentinel - Workspace Management Endpoints.

Creates workspaces and manages membership with RBAC.
All endpoints require a valid authenticated user (JWT).
"""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies import CurrentUser, get_workspace_service
from app.domain.schemas.workspace import (
    AddMemberRequest,
    ChangeRoleRequest,
    MemberListResponse,
    MemberResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Workspace",
    description="Create a new brand workspace. The caller is automatically added as OWNER.",
)
async def create_workspace(
    body: WorkspaceCreateRequest,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    ws = await svc.create_workspace(
        name=body.name,
        description=body.description,
        actor_user_id=str(current_user.id),
        actor_email=current_user.email,
    )
    return WorkspaceResponse.model_validate(ws)


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List My Workspaces",
    description="Return all workspaces the authenticated user is an active member of.",
)
async def list_my_workspaces(
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceResponse]:
    workspaces = await svc.list_my_workspaces(str(current_user.id))
    return [WorkspaceResponse.model_validate(ws) for ws in workspaces]


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get Workspace",
    description="Return workspace details. Requires active membership.",
)
async def get_workspace(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    ws = await svc.get_workspace(workspace_id, str(current_user.id))
    return WorkspaceResponse.model_validate(ws)


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


@router.get(
    "/{workspace_id}/members",
    response_model=MemberListResponse,
    summary="List Members",
    description="List all members of a workspace. Requires active membership.",
)
async def list_members(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> MemberListResponse:
    members = await svc.list_members(workspace_id, str(current_user.id))
    return MemberListResponse(
        workspace_id=workspace_id,
        members=[MemberResponse.model_validate(m) for m in members],
        total=len(members),
    )


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Member",
    description="Add a user to a workspace. Requires OWNER or ADMIN role.",
)
async def add_member(
    workspace_id: uuid.UUID,
    body: AddMemberRequest,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> MemberResponse:
    member = await svc.add_member(
        workspace_id=workspace_id,
        target_user_id=body.user_id,
        target_email=str(body.email),
        role=body.role,
        actor_user_id=str(current_user.id),
    )
    return MemberResponse.model_validate(member)


@router.patch(
    "/{workspace_id}/members/{target_user_id}/role",
    response_model=MemberResponse,
    summary="Change Member Role",
    description="Change a member's role. Requires OWNER role.",
)
async def change_member_role(
    workspace_id: uuid.UUID,
    target_user_id: str,
    body: ChangeRoleRequest,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> MemberResponse:
    member = await svc.change_member_role(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        new_role=body.role,
        actor_user_id=str(current_user.id),
    )
    return MemberResponse.model_validate(member)


@router.delete(
    "/{workspace_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Member",
    description="Remove a member from a workspace. OWNER or ADMIN required.",
)
async def remove_member(
    workspace_id: uuid.UUID,
    target_user_id: str,
    current_user: CurrentUser,
    svc: WorkspaceService = Depends(get_workspace_service),
) -> None:
    await svc.remove_member(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        actor_user_id=str(current_user.id),
    )
