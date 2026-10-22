"""Inkloom Sentinel - Foundational Audit Service.

Provides an append-only interface for recording domain events and compliance actions.
Ensures sensitive user client data (like IP) is safely hashed before persistence.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_sensitive_identifier
from app.domain.enums import AuditEventType
from app.domain.models.audit import AuditEvent

logger = get_logger(__name__)


class AuditService:
    """Service governing immutable, append-only domain event logging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        event_payload: dict[str, Any],
        workspace_id: uuid.UUID | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Create and persist an immutable audit event entry."""
        # Privacy-preserving hash of client IP
        ip_hash = hash_sensitive_identifier(client_ip) if client_ip else None
        ua_snippet = user_agent[:120] if user_agent else None

        event = AuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_payload=event_payload,
            ip_address_hash=ip_hash,
            user_agent_snippet=ua_snippet,
        )

        self.session.add(event)
        # Flush to generate ID and timestamp without committing the outer transaction prematurely
        await self.session.flush()

        logger.info(
            "audit_event_recorded",
            event_type=event_type.value,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            audit_id=str(event.id),
        )
        return event

    async def list_workspace_audit_timeline(
        self,
        workspace_id: uuid.UUID,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        submission_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        resolve_references: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve paginated, chronological audit timeline strictly scoped to a workspace.

        Supports filtering by:
        - event_type (enum)
        - actor_id (string)
        - date range (start_date, end_date)
        - related submission_id (direct resource or embedded payload reference)

        Maintains stable ordering: occurred_at DESC, id DESC.
        Safely handles referenced entities that may be deleted or unavailable.
        """
        from sqlalchemy import func, or_, select

        base_query = select(AuditEvent).where(AuditEvent.workspace_id == workspace_id)

        if event_type is not None:
            base_query = base_query.where(AuditEvent.event_type == event_type)

        if actor_id is not None:
            base_query = base_query.where(AuditEvent.actor_id == actor_id)

        if start_date is not None:
            base_query = base_query.where(AuditEvent.occurred_at >= start_date)

        if end_date is not None:
            base_query = base_query.where(AuditEvent.occurred_at <= end_date)

        if submission_id is not None:
            sub_id_str = str(submission_id)
            base_query = base_query.where(
                or_(
                    AuditEvent.resource_id == sub_id_str,
                    AuditEvent.event_payload["submission_id"].as_string() == sub_id_str,
                )
            )

        # Count total matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Stable pagination
        offset = (page - 1) * page_size
        paged_query = (
            base_query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(paged_query)
        events = result.scalars().all()

        if not resolve_references or not events:
            return [
                {
                    "id": ev.id,
                    "workspace_id": ev.workspace_id,
                    "event_type": ev.event_type,
                    "actor_id": ev.actor_id,
                    "resource_type": ev.resource_type,
                    "resource_id": ev.resource_id,
                    "event_payload": ev.event_payload,
                    "ip_address_hash": ev.ip_address_hash,
                    "user_agent_snippet": ev.user_agent_snippet,
                    "occurred_at": ev.occurred_at,
                    "related_entity": None,
                }
                for ev in events
            ], total

        # Batch resolve related entities safely
        resolved_entities = await self._batch_resolve_entities(workspace_id, events)

        items = []
        for ev in events:
            entity_ref = resolved_entities.get((ev.resource_type, ev.resource_id))
            items.append(
                {
                    "id": ev.id,
                    "workspace_id": ev.workspace_id,
                    "event_type": ev.event_type,
                    "actor_id": ev.actor_id,
                    "resource_type": ev.resource_type,
                    "resource_id": ev.resource_id,
                    "event_payload": ev.event_payload,
                    "ip_address_hash": ev.ip_address_hash,
                    "user_agent_snippet": ev.user_agent_snippet,
                    "occurred_at": ev.occurred_at,
                    "related_entity": entity_ref,
                }
            )

        return items, total

    async def _batch_resolve_entities(
        self, workspace_id: uuid.UUID, events: list[AuditEvent]
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Batch-resolve related entity references without raising if entities were deleted."""
        from sqlalchemy import select

        from app.domain.models.evidence import EvidenceSource
        from app.domain.models.policy import BrandPolicy, PolicyGuideline
        from app.domain.models.review import CorrectionSuggestion, ReviewDecision
        from app.domain.models.semantic import SemanticReviewRun
        from app.domain.models.submission import ContentRevision, ContentSubmission
        from app.domain.models.verification import VerificationRun

        # Group valid UUIDs by resource type
        ids_by_type: dict[str, set[uuid.UUID]] = {}
        for ev in events:
            try:
                parsed_id = uuid.UUID(ev.resource_id)
                ids_by_type.setdefault(ev.resource_type, set()).add(parsed_id)
            except (ValueError, TypeError, AttributeError):
                continue

        resolved: dict[tuple[str, str], dict[str, Any]] = {}

        # 1. ContentSubmission
        if "ContentSubmission" in ids_by_type:
            q = select(ContentSubmission).where(
                ContentSubmission.id.in_(ids_by_type["ContentSubmission"]),
                ContentSubmission.workspace_id == workspace_id,
            )
            subs = (await self.session.execute(q)).scalars().all()
            for s in subs:
                resolved[("ContentSubmission", str(s.id))] = {
                    "resource_type": "ContentSubmission",
                    "resource_id": str(s.id),
                    "display_name": s.title,
                    "is_available": True,
                    "details": {"status": s.status.value, "campaign_tag": s.campaign_tag},
                }

        # 2. ContentRevision
        if "ContentRevision" in ids_by_type:
            q = (
                select(ContentRevision)
                .join(ContentSubmission)
                .where(
                    ContentRevision.id.in_(ids_by_type["ContentRevision"]),
                    ContentSubmission.workspace_id == workspace_id,
                )
            )
            revs = (await self.session.execute(q)).scalars().all()
            for r in revs:
                resolved[("ContentRevision", str(r.id))] = {
                    "resource_type": "ContentRevision",
                    "resource_id": str(r.id),
                    "display_name": f"Revision #{r.revision_number}",
                    "is_available": True,
                    "details": {
                        "submission_id": str(r.submission_id),
                        "revision_number": r.revision_number,
                    },
                }

        # 3. BrandPolicy
        if "BrandPolicy" in ids_by_type:
            q = select(BrandPolicy).where(
                BrandPolicy.id.in_(ids_by_type["BrandPolicy"]),
                BrandPolicy.workspace_id == workspace_id,
            )
            pols = (await self.session.execute(q)).scalars().all()
            for p in pols:
                resolved[("BrandPolicy", str(p.id))] = {
                    "resource_type": "BrandPolicy",
                    "resource_id": str(p.id),
                    "display_name": p.name,
                    "is_available": True,
                    "details": {"version": p.version, "status": p.status.value},
                }

        # 4. PolicyGuideline
        if "PolicyGuideline" in ids_by_type:
            q = (
                select(PolicyGuideline)
                .join(BrandPolicy)
                .where(
                    PolicyGuideline.id.in_(ids_by_type["PolicyGuideline"]),
                    BrandPolicy.workspace_id == workspace_id,
                )
            )
            guides = (await self.session.execute(q)).scalars().all()
            for g in guides:
                resolved[("PolicyGuideline", str(g.id))] = {
                    "resource_type": "PolicyGuideline",
                    "resource_id": str(g.id),
                    "display_name": g.title,
                    "is_available": True,
                    "details": {"category": g.category.value, "rule_type": g.rule_type},
                }

        # 5. EvidenceSource
        if "EvidenceSource" in ids_by_type:
            q = select(EvidenceSource).where(
                EvidenceSource.id.in_(ids_by_type["EvidenceSource"]),
                EvidenceSource.workspace_id == workspace_id,
            )
            srcs = (await self.session.execute(q)).scalars().all()
            for src in srcs:
                resolved[("EvidenceSource", str(src.id))] = {
                    "resource_type": "EvidenceSource",
                    "resource_id": str(src.id),
                    "display_name": src.title,
                    "is_available": True,
                    "details": {
                        "source_type": src.source_type.value,
                        "approval_status": src.approval_status.value,
                    },
                }

        # 6. VerificationRun
        if "VerificationRun" in ids_by_type:
            q = (
                select(VerificationRun)
                .join(ContentRevision)
                .join(ContentSubmission)
                .where(
                    VerificationRun.id.in_(ids_by_type["VerificationRun"]),
                    ContentSubmission.workspace_id == workspace_id,
                )
            )
            vruns = (await self.session.execute(q)).scalars().all()
            for vr in vruns:
                resolved[("VerificationRun", str(vr.id))] = {
                    "resource_type": "VerificationRun",
                    "resource_id": str(vr.id),
                    "display_name": f"Verification Run (v{vr.policy_version})",
                    "is_available": True,
                    "details": {
                        "status": vr.status,
                        "violation_count": vr.violation_count,
                        "total_rules": vr.total_rules,
                    },
                }

        # 7. SemanticReviewRun
        if "SemanticReviewRun" in ids_by_type:
            q = select(SemanticReviewRun).where(
                SemanticReviewRun.id.in_(ids_by_type["SemanticReviewRun"]),
                SemanticReviewRun.workspace_id == workspace_id,
            )
            sruns = (await self.session.execute(q)).scalars().all()
            for sr in sruns:
                resolved[("SemanticReviewRun", str(sr.id))] = {
                    "resource_type": "SemanticReviewRun",
                    "resource_id": str(sr.id),
                    "display_name": f"Semantic Review ({sr.overall_outcome.value})",
                    "is_available": True,
                    "details": {
                        "overall_outcome": sr.overall_outcome.value,
                        "violation_count": sr.violation_count,
                    },
                }

        # 8. CorrectionSuggestion
        if "CorrectionSuggestion" in ids_by_type:
            q = select(CorrectionSuggestion).where(
                CorrectionSuggestion.id.in_(ids_by_type["CorrectionSuggestion"]),
                CorrectionSuggestion.workspace_id == workspace_id,
            )
            sugs = (await self.session.execute(q)).scalars().all()
            for sug in sugs:
                resolved[("CorrectionSuggestion", str(sug.id))] = {
                    "resource_type": "CorrectionSuggestion",
                    "resource_id": str(sug.id),
                    "display_name": f"Correction ({sug.status.value})",
                    "is_available": True,
                    "details": {
                        "status": sug.status.value,
                        "recommended_action": sug.recommended_action[:60],
                    },
                }

        # 9. ReviewDecision
        if "ReviewDecision" in ids_by_type:
            q = (
                select(ReviewDecision)
                .join(ContentSubmission)
                .where(
                    ReviewDecision.id.in_(ids_by_type["ReviewDecision"]),
                    ContentSubmission.workspace_id == workspace_id,
                )
            )
            decs = (await self.session.execute(q)).scalars().all()
            for d in decs:
                resolved[("ReviewDecision", str(d.id))] = {
                    "resource_type": "ReviewDecision",
                    "resource_id": str(d.id),
                    "display_name": f"Review Decision: {d.decision.value}",
                    "is_available": True,
                    "details": {
                        "decision": d.decision.value,
                        "reviewer_id": d.reviewer_id,
                    },
                }

        # Populate fallback for missing or deleted entities
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for ev in events:
            key = (ev.resource_type, ev.resource_id)
            if key in resolved:
                result[key] = resolved[key]
            else:
                result[key] = {
                    "resource_type": ev.resource_type,
                    "resource_id": ev.resource_id,
                    "display_name": None,
                    "is_available": False,
                    "details": {"note": "Referenced entity is unavailable or has been deleted."},
                }

        return result
