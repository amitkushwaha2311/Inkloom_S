"""Inkloom Sentinel - Workspace Management Pydantic Schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import WorkspaceRole


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Workspace display name")
    description: str | None = Field(None, max_length=500)


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: str
    email: str
    role: WorkspaceRole
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: str = Field(
        ..., min_length=1, max_length=64, description="Target user's UUID as string"
    )
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.CONTRIBUTOR


class ChangeRoleRequest(BaseModel):
    role: WorkspaceRole


class MemberListResponse(BaseModel):
    workspace_id: uuid.UUID
    members: list[MemberResponse]
    total: int
