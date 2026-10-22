"""Inkloom Sentinel - Workspace Audit Trail & Governance Analytics Endpoints.

Routes for:
- Paginated, filterable chronological audit event listings with referenced entity resolution.
- Read-only submission lifecycle provenance across revisions, policies, findings, and decisions.
- Governance and compliance analytics metrics across categories, severities, and historical trends.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    CurrentUser,
    get_analytics_service,
    get_audit_service,
    get_workspace_service,
)
from app.domain.enums import AuditEventType
from app.domain.schemas.audit import (
    AuditEventListResponse,
    AuditEventResponse,
    GovernanceAnalyticsResponse,
    SubmissionProvenanceResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import AuditService
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["Audit & Governance Analytics"],
)


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    summary="List Workspace Audit Events",
    description=(
        "Retrieve a paginated, chronological timeline of append-only audit events strictly "
        "scoped to the current workspace. Supports filtering by event type, actor, date range, "
        "and related content submission. Safely handles references to deleted or unavailable entities."
    ),
)
async def list_workspace_audit_events(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    event_type: AuditEventType | None = Query(None, description="Filter by event classification"),
    actor_id: str | None = Query(None, description="Filter by initiating actor identifier"),
    start_date: datetime | None = Query(None, description="Filter events on or after UTC datetime"),
    end_date: datetime | None = Query(None, description="Filter events on or before UTC datetime"),
    submission_id: uuid.UUID | None = Query(
        None, description="Filter events directly or indirectly related to a submission"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    resolve_references: bool = Query(
        True, description="Whether to resolve related entity titles and availability status"
    ),
    audit_svc: AuditService = Depends(get_audit_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> AuditEventListResponse:
    """List audit events in the workspace with pagination, ordering, and optional filters."""
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))

    raw_items, total = await audit_svc.list_workspace_audit_timeline(
        workspace_id=workspace_id,
        event_type=event_type,
        actor_id=actor_id,
        start_date=start_date,
        end_date=end_date,
        submission_id=submission_id,
        page=page,
        page_size=page_size,
        resolve_references=resolve_references,
    )

    items = [AuditEventResponse(**item) for item in raw_items]
    return AuditEventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/submissions/{submission_id}/provenance",
    response_model=SubmissionProvenanceResponse,
    summary="Get Submission Provenance & Review History",
    description=(
        "Retrieve a comprehensive, read-only lifecycle provenance of a content submission. "
        "Traces each revision's content hash, policy versions used, deterministic verification runs, "
        "extracted claims and evidence-source versions, semantic review findings, correction suggestions, "
        "and human review determinations. Explicitly distinguishes missing historical data from clean results."
    ),
)
async def get_submission_provenance(
    workspace_id: uuid.UUID,
    submission_id: uuid.UUID,
    current_user: CurrentUser,
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> SubmissionProvenanceResponse:
    """Return full lifecycle provenance and review audit trail for a content submission."""
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    return await analytics_svc.get_submission_provenance(
        workspace_id=workspace_id,
        submission_id=submission_id,
    )


@router.get(
    "/governance-analytics",
    response_model=GovernanceAnalyticsResponse,
    summary="Get Workspace Governance Analytics",
    description=(
        "Retrieve accurately computed brand governance analytics including completed reviews count, "
        "violations aggregated by category and severity, most frequent guideline violations, "
        "human intervention percentage, correction suggestion acceptance rates, review turnaround duration, "
        "and chronological time-series trends over an optional time window. Safely handles empty datasets."
    ),
)
async def get_governance_analytics(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    start_date: datetime | None = Query(
        None, description="Start of historical analysis window (UTC)"
    ),
    end_date: datetime | None = Query(None, description="End of historical analysis window (UTC)"),
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
    ws_svc: WorkspaceService = Depends(get_workspace_service),
) -> GovernanceAnalyticsResponse:
    """Compute and return workspace-scoped governance and compliance analytics."""
    await ws_svc.verify_workspace_access(workspace_id, str(current_user.id))
    return await analytics_svc.get_governance_analytics(
        workspace_id=workspace_id,
        start_date=start_date,
        end_date=end_date,
    )
