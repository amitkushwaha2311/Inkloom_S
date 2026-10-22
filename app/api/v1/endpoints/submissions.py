"""Inkloom Sentinel - Content Submission & Revision Endpoints.

Routes for content draft ingestion, metadata management, and immutable revision tracking
under workspace authorization and role-based access control.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_submission_service,
    get_workspace_service,
)
from app.core.errors import ForbiddenError
from app.domain.enums import SubmissionStatus, WorkspaceRole
from app.domain.schemas.submission import (
    ContentRevisionCreate,
    ContentRevisionResponse,
    ContentSubmissionCreate,
    ContentSubmissionDetailResponse,
    ContentSubmissionListResponse,
    ContentSubmissionResponse,
    ContentSubmissionUpdate,
)
from app.services.submission_service import (
    SubmissionService,
    serialize_revision,
    serialize_submission,
    serialize_submission_detail,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/submissions",
    tags=["Content Submissions"],
)

# Roles permitted to create submissions or append revisions
_CONTENT_WRITERS = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
    WorkspaceRole.CONTRIBUTOR,
}

# Roles permitted to edit any submission's metadata
_WORKSPACE_MANAGERS = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}


# ---------------------------------------------------------------------------
# Submission CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ContentSubmissionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Content Submission",
    description=(
        "Create a new content submission with its initial (v1) immutable revision. "
        "Requires CONTRIBUTOR role or above. Content is hashed (SHA-256) for tamper detection."
    ),
)
async def create_submission(
    workspace_id: uuid.UUID,
    body: ContentSubmissionCreate,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentSubmissionDetailResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_CONTENT_WRITERS
    )
    submission = await svc.create_submission(
        workspace_id=workspace_id,
        data=body,
        author_id=str(current_user.id),
    )
    return serialize_submission_detail(submission)


@router.get(
    "",
    response_model=ContentSubmissionListResponse,
    summary="List Content Submissions",
    description="List submissions in this workspace with optional filtering and pagination.",
)
async def list_submissions(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    campaign_tag: str | None = Query(None),
    author_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentSubmissionListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items, total = await svc.list_submissions(
        workspace_id=workspace_id,
        status=status_filter,
        campaign_tag=campaign_tag,
        author_id=author_id,
        page=page,
        page_size=page_size,
    )
    return ContentSubmissionListResponse(
        items=[serialize_submission(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/{submission_id}",
    response_model=ContentSubmissionDetailResponse,
    summary="Get Submission Details",
    description="Retrieve a submission with its full revision history.",
)
async def get_submission(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentSubmissionDetailResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    submission = await svc.get_submission_or_404(submission_id, workspace_id)
    return serialize_submission_detail(submission)


@router.patch(
    "/{submission_id}",
    response_model=ContentSubmissionResponse,
    summary="Update Submission Metadata",
    description=(
        "Update metadata (title, campaign_tag, status). Content text CANNOT be edited "
        "via this endpoint — edits must create a new revision."
    ),
)
async def update_submission(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    body: ContentSubmissionUpdate,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentSubmissionResponse:
    member = await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_CONTENT_WRITERS
    )
    submission = await svc.get_submission_or_404(submission_id, workspace_id)

    # Authorization: only author or workspace managers (OWNER / ADMIN) can edit metadata
    if submission.author_id != str(current_user.id) and member.role not in _WORKSPACE_MANAGERS:
        raise ForbiddenError("Only the author or a workspace manager can edit this submission.")

    updated = await svc.update_submission_metadata(
        submission_id=submission_id,
        workspace_id=workspace_id,
        data=body,
        actor_id=str(current_user.id),
    )
    return serialize_submission(updated)


# ---------------------------------------------------------------------------
# Revision Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{submission_id}/revisions",
    response_model=ContentRevisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Content Revision",
    description=(
        "Create a new immutable revision for an existing submission. "
        "Pass expected_revision_number for optimistic concurrency control to prevent lost updates."
    ),
)
async def create_revision(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    body: ContentRevisionCreate,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentRevisionResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_CONTENT_WRITERS
    )
    revision = await svc.create_revision(
        submission_id=submission_id,
        workspace_id=workspace_id,
        data=body,
        actor_id=str(current_user.id),
    )
    return serialize_revision(revision)


@router.get(
    "/{submission_id}/revisions",
    response_model=list[ContentRevisionResponse],
    summary="List Revisions",
    description="List all revisions for a content submission in sequential order.",
)
async def list_revisions(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> list[ContentRevisionResponse]:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    revisions = await svc.list_revisions(submission_id, workspace_id)
    return [serialize_revision(r) for r in revisions]


@router.get(
    "/{submission_id}/revisions/{revision_number}",
    response_model=ContentRevisionResponse,
    summary="Get Specific Revision",
    description="Retrieve a specific immutable revision by its revision number.",
)
async def get_revision(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: SubmissionService = Depends(get_submission_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> ContentRevisionResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    revision = await svc.get_revision_or_404(submission_id, workspace_id, revision_number)
    return serialize_revision(revision)
