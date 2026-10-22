"""Inkloom Sentinel - Evidence Sources & Claim Verification Endpoints.

Workspace-scoped, JWT-authenticated endpoints for:
- Registering, reviewing, approving, rejecting, and revoking authoritative evidence sources.
- Recording content claims against specific content revisions.
- Running conservative, evidence-backed assessments on claims.
- Retrieving immutable claim assessment history.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_claim_service,
    get_workspace_service,
)
from app.domain.enums import ClaimType, SourceApprovalStatus, WorkspaceRole
from app.domain.models.evidence import ContentClaim, EvidenceSource
from app.domain.schemas.evidence import (
    ClaimAssessmentListResponse,
    ClaimAssessmentRequest,
    ClaimAssessmentResponse,
    ClaimAssessmentSnapshot,
    ClaimDiscoveryResponse,
    ContentClaimCreate,
    ContentClaimListResponse,
    ContentClaimResponse,
    ContentClaimUpdate,
    EvidenceSourceCreate,
    EvidenceSourceListResponse,
    EvidenceSourceRejectRequest,
    EvidenceSourceResponse,
    EvidenceSourceRevokeRequest,
    EvidenceSourceUpdate,
)
from app.services.claim_service import ClaimService
from app.services.workspace_service import WorkspaceService

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

sources_router = APIRouter(
    prefix="/workspaces/{workspace_id}/evidence-sources",
    tags=["Evidence Sources"],
)

claims_router = APIRouter(
    prefix="/workspaces/{workspace_id}/submissions/{submission_id}/revisions/{revision_number}/claims",
    tags=["Content Claims"],
)

# Role definitions
_WRITE_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.REVIEWER,
    WorkspaceRole.CONTRIBUTOR,
}

_ADMIN_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
}

# Type aliases for dependency injection
ClaimSvc = Annotated[ClaimService, Depends(get_claim_service)]
WsSvc = Annotated[WorkspaceService, Depends(get_workspace_service)]


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------


def _serialize_source(source: EvidenceSource) -> EvidenceSourceResponse:
    data = EvidenceSourceResponse.model_validate(source)
    data.is_valid = source.is_currently_valid()
    return data


def _serialize_claim(claim: ContentClaim) -> ContentClaimResponse:
    latest = None
    if "assessments" in claim.__dict__ and claim.assessments:
        latest = ClaimAssessmentSnapshot.model_validate(claim.assessments[0])
    return ContentClaimResponse(
        id=claim.id,
        workspace_id=claim.workspace_id,
        revision_id=claim.revision_id,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        context_excerpt=claim.context_excerpt,
        char_start=claim.char_start,
        char_end=claim.char_end,
        discovery_status=claim.discovery_status,
        extraction_method=claim.extraction_method,
        extraction_version=claim.extraction_version,
        reviewed_by_id=claim.reviewed_by_id,
        reviewed_at=claim.reviewed_at,
        created_by_id=claim.created_by_id,
        latest_assessment=latest,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


# ---------------------------------------------------------------------------
# Evidence Sources Endpoints
# ---------------------------------------------------------------------------


@sources_router.post(
    "",
    response_model=EvidenceSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Evidence Source",
    description="Registers an authoritative evidence source in DRAFT status. Requires CONTRIBUTOR or above.",
)
async def create_evidence_source(
    workspace_id: uuid.UUID,
    body: EvidenceSourceCreate,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    source = await svc.create_evidence_source(
        workspace_id=workspace_id, body=body, actor_id=str(current_user.id)
    )
    return _serialize_source(source)


@sources_router.get(
    "",
    response_model=EvidenceSourceListResponse,
    summary="List Evidence Sources",
    description="Lists evidence sources in the workspace. Requires active workspace membership.",
)
async def list_evidence_sources(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
    approval_status: Annotated[
        SourceApprovalStatus | None, Query(description="Filter by approval status")
    ] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type")] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EvidenceSourceListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items, total = await svc.list_evidence_sources(
        workspace_id=workspace_id,
        approval_status=approval_status,
        source_type=source_type,
        page=page,
        page_size=page_size,
    )
    return EvidenceSourceListResponse(
        items=[_serialize_source(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@sources_router.get(
    "/{source_id}",
    response_model=EvidenceSourceResponse,
    summary="Get Evidence Source",
    description="Retrieves an evidence source by ID. Requires active workspace membership.",
)
async def get_evidence_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    source = await svc.get_evidence_source(workspace_id, source_id)
    return _serialize_source(source)


@sources_router.patch(
    "/{source_id}",
    response_model=EvidenceSourceResponse,
    summary="Update Evidence Source",
    description=(
        "Updates an evidence source. If the source is already APPROVED, bumping excerpts "
        "or facts increments its version and resets status to DRAFT for re-review."
    ),
)
async def update_evidence_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    body: EvidenceSourceUpdate,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    source = await svc.update_evidence_source(
        workspace_id=workspace_id, source_id=source_id, body=body, actor_id=str(current_user.id)
    )
    return _serialize_source(source)


@sources_router.post(
    "/{source_id}/approve",
    response_model=EvidenceSourceResponse,
    summary="Approve Evidence Source",
    description="Approves an evidence source for authoritative verification use. Requires OWNER or ADMIN.",
)
async def approve_evidence_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_ADMIN_ROLES
    )
    source = await svc.approve_evidence_source(
        workspace_id=workspace_id, source_id=source_id, actor_id=str(current_user.id)
    )
    return _serialize_source(source)


@sources_router.post(
    "/{source_id}/reject",
    response_model=EvidenceSourceResponse,
    summary="Reject Evidence Source",
    description="Rejects an evidence source with a required justification. Requires OWNER or ADMIN.",
)
async def reject_evidence_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    body: EvidenceSourceRejectRequest,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_ADMIN_ROLES
    )
    source = await svc.reject_evidence_source(
        workspace_id=workspace_id,
        source_id=source_id,
        actor_id=str(current_user.id),
        reason=body.reason,
    )
    return _serialize_source(source)


@sources_router.post(
    "/{source_id}/revoke",
    response_model=EvidenceSourceResponse,
    summary="Revoke Evidence Source",
    description="Revokes approval of an evidence source. Requires OWNER or ADMIN.",
)
async def revoke_evidence_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    body: EvidenceSourceRevokeRequest,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> EvidenceSourceResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_ADMIN_ROLES
    )
    source = await svc.revoke_evidence_source(
        workspace_id=workspace_id,
        source_id=source_id,
        actor_id=str(current_user.id),
        reason=body.reason,
    )
    return _serialize_source(source)


# ---------------------------------------------------------------------------
# Content Claims & Assessment Endpoints
# ---------------------------------------------------------------------------


@claims_router.post(
    "",
    response_model=ContentClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Content Claim",
    description="Records a discrete claim against a content revision. Requires CONTRIBUTOR or above.",
)
async def record_claim(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    body: ContentClaimCreate,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ContentClaimResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    claim = await svc.record_claim(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        body=body,
        actor_id=str(current_user.id),
    )
    return _serialize_claim(claim)


@claims_router.post(
    "/discover",
    response_model=ClaimDiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Discover Candidate Claims",
    description=(
        "Automatically identifies candidate factual claims, opinions, and promotional statements "
        "from a revision. Deduplicates against existing claims. Requires CONTRIBUTOR or above."
    ),
)
async def discover_claims(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ClaimDiscoveryResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    new_claims, existing_count = await svc.discover_claims(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        actor_id=str(current_user.id),
    )
    revision = await svc._require_revision(submission_id, workspace_id, revision_number)
    return ClaimDiscoveryResponse(
        revision_id=revision.id,
        discovered_count=len(new_claims),
        existing_count=existing_count,
        claims=[_serialize_claim(c) for c in new_claims],
    )


@claims_router.get(
    "",
    response_model=ContentClaimListResponse,
    summary="List Content Claims",
    description="Lists claims recorded on a revision. Requires active workspace membership.",
)
async def list_claims(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
    claim_type: Annotated[ClaimType | None, Query(description="Filter by claim type")] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContentClaimListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    claims, total = await svc.list_claims(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_type=claim_type,
        page=page,
        page_size=page_size,
    )
    return ContentClaimListResponse(
        items=[_serialize_claim(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@claims_router.get(
    "/{claim_id}",
    response_model=ContentClaimResponse,
    summary="Get Content Claim",
    description="Retrieves a content claim by ID. Requires active workspace membership.",
)
async def get_claim(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    claim_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ContentClaimResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    claim = await svc.get_claim(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_id=claim_id,
    )
    return _serialize_claim(claim)


@claims_router.patch(
    "/{claim_id}",
    response_model=ContentClaimResponse,
    summary="Update or Review Content Claim",
    description="Updates, confirms, dismisses, or reclassifies a claim candidate. Requires CONTRIBUTOR or above.",
)
async def update_claim(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    claim_id: uuid.UUID,
    body: ContentClaimUpdate,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ContentClaimResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    claim = await svc.update_claim(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_id=claim_id,
        body=body,
        actor_id=str(current_user.id),
    )
    return _serialize_claim(claim)


@claims_router.post(
    "/{claim_id}/assess",
    response_model=ClaimAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assess Content Claim",
    description=(
        "Performs a conservative evidence assessment of a claim against active, approved evidence sources. "
        "Requires CONTRIBUTOR or above. Preserves immutability: Re-assessing creates a new assessment result."
    ),
)
async def assess_claim(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    claim_id: uuid.UUID,
    body: ClaimAssessmentRequest,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ClaimAssessmentResponse:
    await ws_svc.verify_workspace_access(
        workspace_id, str(current_user.id), minimum_roles=_WRITE_ROLES
    )
    assessment = await svc.assess_claim(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_id=claim_id,
        actor_id=str(current_user.id),
        policy_id=body.policy_id,
    )
    return ClaimAssessmentResponse.model_validate(assessment)


@claims_router.get(
    "/{claim_id}/assessments",
    response_model=ClaimAssessmentListResponse,
    summary="List Claim Assessments",
    description="Lists historical assessments for a claim in chronological order. Requires active workspace membership.",
)
async def list_claim_assessments(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    claim_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ClaimAssessmentListResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    items, total = await svc.list_claim_assessments(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_id=claim_id,
        page=page,
        page_size=page_size,
    )
    return ClaimAssessmentListResponse(
        items=[ClaimAssessmentResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@claims_router.get(
    "/{claim_id}/assessments/{assessment_id}",
    response_model=ClaimAssessmentResponse,
    summary="Get Claim Assessment",
    description="Retrieves a specific claim assessment result. Requires active workspace membership.",
)
async def get_claim_assessment(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    revision_number: int,
    claim_id: uuid.UUID,
    assessment_id: uuid.UUID,
    current_user: CurrentUser,
    svc: ClaimSvc,
    ws_svc: WsSvc,
) -> ClaimAssessmentResponse:
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    assessment = await svc.get_claim_assessment(
        workspace_id=workspace_id,
        submission_id=submission_id,
        revision_number=revision_number,
        claim_id=claim_id,
        assessment_id=assessment_id,
    )
    return ClaimAssessmentResponse.model_validate(assessment)
