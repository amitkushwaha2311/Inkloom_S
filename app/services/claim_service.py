"""Inkloom Sentinel - Evidence Source Registry & Claim Assessment Service.

Manages approved authoritative evidence sources, records content claims,
and performs conservative, evidence-backed claim verification.
"""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    ClaimAssessmentStatus,
    ClaimDiscoveryStatus,
    ClaimType,
    PolicyStatus,
    SourceApprovalStatus,
)
from app.domain.models.evidence import ClaimAssessment, ContentClaim, EvidenceSource
from app.domain.models.policy import BrandPolicy
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.domain.schemas.evidence import (
    ContentClaimCreate,
    ContentClaimUpdate,
    EvidenceSourceCreate,
    EvidenceSourceUpdate,
)
from app.services.audit_service import AuditService
from app.services.extraction_service import BaseClaimExtractor, RuleBasedClaimExtractor

logger = get_logger(__name__)

ENGINE_VERSION = "sentinel-claim-v1.0"


def _clean_tokens(text: str) -> set[str]:
    """Normalize and extract alphanumeric word tokens."""
    return set(re.findall(r"\b[a-zA-Z0-9]+\b", text.lower()))


def _evaluate_source_match(
    claim_text: str, source: EvidenceSource
) -> tuple[bool, bool, str | None]:
    """Evaluate whether an evidence source supports, contradicts, or has no stance on a claim.

    Returns:
        (is_support, is_contradiction, evidence_excerpt)
    """
    claim_lower = claim_text.strip().lower()
    claim_tokens = _clean_tokens(claim_text)

    # 1. Evaluate structured facts
    for fact in source.structured_facts or []:
        if not isinstance(fact, dict):
            continue

        # Check explicit contradiction terms
        contradicts_list = fact.get("contradicts") or []
        if isinstance(contradicts_list, str):
            contradicts_list = [contradicts_list]
        for c in contradicts_list:
            if isinstance(c, str) and c.strip().lower() in claim_lower:
                return False, True, c.strip()

        # Check explicit support terms
        supports_list = fact.get("supports") or []
        if isinstance(supports_list, str):
            supports_list = [supports_list]
        for s in supports_list:
            if isinstance(s, str) and s.strip().lower() in claim_lower:
                return True, False, s.strip()

        # Check keywords matching
        kw_list = fact.get("keywords") or []
        if isinstance(kw_list, list) and kw_list:
            kw_tokens = {k.strip().lower() for k in kw_list if isinstance(k, str)}
            if kw_tokens and kw_tokens.issubset(claim_tokens):
                fact_type = fact.get("type", "support")
                assertion = fact.get("assertion") or fact.get("statement") or str(fact)
                if fact_type == "contradiction":
                    return False, True, str(assertion)
                return True, False, str(assertion)

    # 2. Evaluate trusted excerpts
    for excerpt in source.trusted_excerpts or []:
        if not isinstance(excerpt, str):
            continue
        exc_clean = excerpt.strip()
        exc_lower = exc_clean.lower()

        # Check for explicit contradiction prefix in excerpt
        if exc_lower.startswith("[contradicts]") or "[contradicts]" in exc_lower:
            target = exc_lower.replace("[contradicts]", "").strip()
            if target and target in claim_lower:
                return False, True, exc_clean

        # Exact or substring containment
        if exc_lower in claim_lower or claim_lower in exc_lower:
            return True, False, exc_clean

        # High token overlap for substantive excerpts (> 75% common tokens)
        exc_tokens = _clean_tokens(exc_clean)
        if len(exc_tokens) >= 4 and len(claim_tokens) >= 4:
            common = claim_tokens.intersection(exc_tokens)
            overlap_ratio = len(common) / min(len(claim_tokens), len(exc_tokens))
            if overlap_ratio >= 0.8:
                return True, False, exc_clean

    return False, False, None


class ClaimService:
    """Service handling evidence sources, content claims, and conservative claim assessment."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------
    # Evidence Source Management
    # ------------------------------------------------------------------

    async def create_evidence_source(
        self,
        workspace_id: uuid.UUID,
        body: EvidenceSourceCreate,
        actor_id: str,
    ) -> EvidenceSource:
        """Register a new evidence source in DRAFT status."""
        source = EvidenceSource(
            workspace_id=workspace_id,
            title=body.title,
            source_type=body.source_type,
            source_url=body.source_url,
            internal_reference=body.internal_reference,
            publisher_or_owner=body.publisher_or_owner,
            effective_date=body.effective_date,
            expiry_date=body.expiry_date,
            approval_status=SourceApprovalStatus.DRAFT,
            version=1,
            trusted_excerpts=body.trusted_excerpts,
            structured_facts=body.structured_facts,
            created_by_id=actor_id,
        )
        self.session.add(source)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.EVIDENCE_SOURCE_CREATED,
            actor_id=actor_id,
            resource_type="EvidenceSource",
            resource_id=str(source.id),
            workspace_id=workspace_id,
            event_payload={
                "title": source.title,
                "source_type": source.source_type.value,
                "version": source.version,
            },
        )
        return source

    async def get_evidence_source(
        self, workspace_id: uuid.UUID, source_id: uuid.UUID
    ) -> EvidenceSource:
        """Retrieve a single evidence source within the workspace."""
        stmt = select(EvidenceSource).where(
            EvidenceSource.id == source_id,
            EvidenceSource.workspace_id == workspace_id,
        )
        source = (await self.session.execute(stmt)).scalar_one_or_none()
        if source is None:
            raise NotFoundError("EvidenceSource", str(source_id))
        return source

    async def list_evidence_sources(
        self,
        workspace_id: uuid.UUID,
        approval_status: SourceApprovalStatus | None = None,
        source_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvidenceSource], int]:
        """List evidence sources in workspace with optional filters and pagination."""
        filters = [EvidenceSource.workspace_id == workspace_id]
        if approval_status is not None:
            filters.append(EvidenceSource.approval_status == approval_status)
        if source_type is not None:
            filters.append(EvidenceSource.source_type == source_type)

        count_stmt = select(func.count(EvidenceSource.id)).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        items_stmt = (
            select(EvidenceSource)
            .where(*filters)
            .order_by(EvidenceSource.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        items = list((await self.session.execute(items_stmt)).scalars().all())
        return items, total

    async def update_evidence_source(
        self,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        body: EvidenceSourceUpdate,
        actor_id: str,
    ) -> EvidenceSource:
        """Update an evidence source.

        If updating an APPROVED source, bumps the version number and resets status
        to DRAFT to enforce re-approval before new evidence is trusted.
        """
        source = await self.get_evidence_source(workspace_id, source_id)

        bump_version = False
        if source.approval_status == SourceApprovalStatus.APPROVED:
            # Modifying an approved source requires re-review and version bump
            bump_version = True
            source.version += 1
            source.approval_status = SourceApprovalStatus.DRAFT
            source.approved_by_id = None
            source.approved_at = None

        if body.title is not None:
            source.title = body.title
        if body.source_type is not None:
            source.source_type = body.source_type
        if body.source_url is not None:
            source.source_url = body.source_url
        if body.internal_reference is not None:
            source.internal_reference = body.internal_reference
        if body.publisher_or_owner is not None:
            source.publisher_or_owner = body.publisher_or_owner
        if body.effective_date is not None:
            source.effective_date = body.effective_date
        if body.expiry_date is not None:
            source.expiry_date = body.expiry_date
        if body.trusted_excerpts is not None:
            source.trusted_excerpts = body.trusted_excerpts
        if body.structured_facts is not None:
            source.structured_facts = body.structured_facts

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.EVIDENCE_SOURCE_UPDATED,
            actor_id=actor_id,
            resource_type="EvidenceSource",
            resource_id=str(source.id),
            workspace_id=workspace_id,
            event_payload={
                "version": source.version,
                "bumped_version": bump_version,
                "status": source.approval_status.value,
            },
        )
        return source

    async def approve_evidence_source(
        self,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        actor_id: str,
    ) -> EvidenceSource:
        """Approve an evidence source, making it authoritative for verification."""
        source = await self.get_evidence_source(workspace_id, source_id)
        if source.approval_status == SourceApprovalStatus.APPROVED:
            return source

        source.approval_status = SourceApprovalStatus.APPROVED
        source.approved_by_id = actor_id
        source.approved_at = datetime.now(UTC)
        source.rejection_reason = None
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.EVIDENCE_SOURCE_APPROVED,
            actor_id=actor_id,
            resource_type="EvidenceSource",
            resource_id=str(source.id),
            workspace_id=workspace_id,
            event_payload={"version": source.version},
        )
        return source

    async def reject_evidence_source(
        self,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        actor_id: str,
        reason: str,
    ) -> EvidenceSource:
        """Reject an evidence source with a required justification."""
        source = await self.get_evidence_source(workspace_id, source_id)
        source.approval_status = SourceApprovalStatus.REJECTED
        source.rejection_reason = reason
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.EVIDENCE_SOURCE_REJECTED,
            actor_id=actor_id,
            resource_type="EvidenceSource",
            resource_id=str(source.id),
            workspace_id=workspace_id,
            event_payload={"reason": reason, "version": source.version},
        )
        return source

    async def revoke_evidence_source(
        self,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        actor_id: str,
        reason: str,
    ) -> EvidenceSource:
        """Revoke approval of an evidence source."""
        source = await self.get_evidence_source(workspace_id, source_id)
        source.approval_status = SourceApprovalStatus.REVOKED
        source.rejection_reason = reason
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.EVIDENCE_SOURCE_REVOKED,
            actor_id=actor_id,
            resource_type="EvidenceSource",
            resource_id=str(source.id),
            workspace_id=workspace_id,
            event_payload={"reason": reason, "version": source.version},
        )
        return source

    # ------------------------------------------------------------------
    # Content Claims Management
    # ------------------------------------------------------------------

    async def _require_revision(
        self, submission_id: uuid.UUID, workspace_id: uuid.UUID, revision_number: int
    ) -> ContentRevision:
        stmt = (
            select(ContentRevision)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(
                ContentRevision.submission_id == submission_id,
                ContentRevision.revision_number == revision_number,
                ContentSubmission.workspace_id == workspace_id,
            )
        )
        revision = (await self.session.execute(stmt)).scalar_one_or_none()
        if revision is None:
            raise NotFoundError(
                "ContentRevision",
                f"submission={submission_id} revision={revision_number}",
            )
        return revision

    async def record_claim(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        body: ContentClaimCreate,
        actor_id: str,
    ) -> ContentClaim:
        """Record an extracted or manually submitted claim against a content revision."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        claim = ContentClaim(
            workspace_id=workspace_id,
            revision_id=revision.id,
            claim_text=body.claim_text,
            claim_type=body.claim_type,
            context_excerpt=body.context_excerpt,
            char_start=body.char_start,
            char_end=body.char_end,
            discovery_status=ClaimDiscoveryStatus.CONFIRMED,
            created_by_id=actor_id,
        )
        self.session.add(claim)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CLAIM_RECORDED,
            actor_id=actor_id,
            resource_type="ContentClaim",
            resource_id=str(claim.id),
            workspace_id=workspace_id,
            event_payload={
                "revision_id": str(revision.id),
                "claim_type": claim.claim_type.value,
                "revision_number": revision_number,
            },
        )
        return claim

    async def discover_claims(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        actor_id: str,
        extractor: BaseClaimExtractor | None = None,
    ) -> tuple[list[ContentClaim], int]:
        """Automatically identify candidate claims from content revision without duplicate creation."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        # Query existing claims for this revision to prevent duplicates
        stmt = select(ContentClaim).where(
            ContentClaim.revision_id == revision.id,
            ContentClaim.workspace_id == workspace_id,
        )
        existing_claims = list((await self.session.execute(stmt)).scalars().all())
        existing_texts = {c.claim_text.strip().lower() for c in existing_claims}

        active_extractor = extractor or RuleBasedClaimExtractor()
        extracted_candidates = active_extractor.extract_claims(revision.content_text)

        new_claims: list[ContentClaim] = []
        for cand in extracted_candidates:
            normalized = cand.claim_text.strip().lower()
            if normalized in existing_texts:
                continue
            existing_texts.add(normalized)

            claim = ContentClaim(
                workspace_id=workspace_id,
                revision_id=revision.id,
                claim_text=cand.claim_text,
                claim_type=cand.claim_type,
                context_excerpt=cand.context_excerpt,
                char_start=cand.char_start,
                char_end=cand.char_end,
                discovery_status=ClaimDiscoveryStatus.CANDIDATE,
                extraction_method=cand.extraction_method,
                extraction_version=cand.extraction_version,
                created_by_id=actor_id,
            )
            self.session.add(claim)
            new_claims.append(claim)

        if new_claims:
            await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CLAIMS_DISCOVERED,
            actor_id=actor_id,
            resource_type="ContentRevision",
            resource_id=str(revision.id),
            workspace_id=workspace_id,
            event_payload={
                "revision_id": str(revision.id),
                "revision_number": revision_number,
                "discovered_count": len(new_claims),
                "existing_count": len(existing_claims),
                "extraction_method": active_extractor.extraction_method,
                "extraction_version": active_extractor.extraction_version,
            },
        )
        return new_claims, len(existing_claims)

    async def update_claim(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_id: uuid.UUID,
        body: ContentClaimUpdate,
        actor_id: str,
    ) -> ContentClaim:
        """Allow human reviewers to confirm, edit, dismiss, or reclassify candidate claims."""
        claim = await self.get_claim(workspace_id, submission_id, revision_number, claim_id)
        now = datetime.now(UTC)

        if body.claim_text is not None and body.claim_text.strip() != claim.claim_text:
            claim.claim_text = body.claim_text.strip()
            # If text is updated and status wasn't explicitly provided, set to EDITED
            if (
                body.discovery_status is None
                and claim.discovery_status == ClaimDiscoveryStatus.CANDIDATE
            ):
                claim.discovery_status = ClaimDiscoveryStatus.EDITED

        if body.claim_type is not None:
            claim.claim_type = body.claim_type

        if body.discovery_status is not None:
            claim.discovery_status = body.discovery_status

        claim.reviewed_by_id = actor_id
        claim.reviewed_at = now

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CLAIM_UPDATED,
            actor_id=actor_id,
            resource_type="ContentClaim",
            resource_id=str(claim.id),
            workspace_id=workspace_id,
            event_payload={
                "claim_id": str(claim.id),
                "discovery_status": claim.discovery_status.value,
                "claim_type": claim.claim_type.value,
            },
        )
        return claim

    async def get_claim(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_id: uuid.UUID,
    ) -> ContentClaim:
        """Retrieve a specific claim, ensuring revision and workspace isolation."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        stmt = (
            select(ContentClaim)
            .where(
                ContentClaim.id == claim_id,
                ContentClaim.revision_id == revision.id,
                ContentClaim.workspace_id == workspace_id,
            )
            .options(selectinload(ContentClaim.assessments))
        )
        claim = (await self.session.execute(stmt)).scalar_one_or_none()
        if claim is None:
            raise NotFoundError("ContentClaim", str(claim_id))
        return claim

    async def list_claims(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_type: ClaimType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ContentClaim], int]:
        """List claims recorded against a content revision."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        filters = [
            ContentClaim.revision_id == revision.id,
            ContentClaim.workspace_id == workspace_id,
        ]
        if claim_type is not None:
            filters.append(ContentClaim.claim_type == claim_type)

        count_stmt = select(func.count(ContentClaim.id)).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(ContentClaim)
            .where(*filters)
            .options(selectinload(ContentClaim.assessments))
            .order_by(ContentClaim.created_at.asc())
            .limit(page_size)
            .offset(offset)
        )
        claims = list((await self.session.execute(stmt)).scalars().all())
        return claims, total

    # ------------------------------------------------------------------
    # Conservative Claim Assessment
    # ------------------------------------------------------------------

    async def assess_claim(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_id: uuid.UUID,
        actor_id: str,
        policy_id: uuid.UUID | None = None,
    ) -> ClaimAssessment:
        """Perform a conservative, evidence-backed assessment of a claim.

        Preserves historical assessment immutability: Re-assessing creates
        a brand-new ClaimAssessment entry rather than mutating existing rows.
        """
        claim = await self.get_claim(workspace_id, submission_id, revision_number, claim_id)
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        # Optional policy binding check
        policy_version = None
        if policy_id is not None:
            stmt = select(BrandPolicy).where(
                BrandPolicy.id == policy_id,
                BrandPolicy.workspace_id == workspace_id,
            )
            policy = (await self.session.execute(stmt)).scalar_one_or_none()
            if policy is None:
                raise NotFoundError("BrandPolicy", str(policy_id))
            if policy.status != PolicyStatus.ACTIVE:
                raise ValidationError(
                    f"Policy '{policy.name}' (v{policy.version}) has status '{policy.status.value}'. "
                    f"Only ACTIVE policies may be bound to claim assessments."
                )
            policy_version = policy.version

        now = datetime.now(UTC)

        # 1. Distinguish claim type
        if claim.claim_type == ClaimType.OPINION:
            status = ClaimAssessmentStatus.NEEDS_HUMAN_REVIEW
            explanation = (
                "Claim is classified as a subjective opinion or stylistic assertion, "
                "which cannot be empirically verified against factual documentation."
            )
            uncertainty = 0.8
            supporting_snapshots: list[dict] = []
            contradicting_snapshots: list[dict] = []

        elif claim.claim_type == ClaimType.PROMOTIONAL:
            status = ClaimAssessmentStatus.NEEDS_HUMAN_REVIEW
            explanation = (
                "Claim is classified as an unverifiable promotional statement or marketing superlative. "
                "Human reviewer judgment is required to evaluate substantiated promotional bounds."
            )
            uncertainty = 0.9
            supporting_snapshots = []
            contradicting_snapshots = []

        else:
            # Factual claim evaluation against approved, active evidence sources
            stmt_sources = select(EvidenceSource).where(
                EvidenceSource.workspace_id == workspace_id,
                EvidenceSource.approval_status == SourceApprovalStatus.APPROVED,
            )
            all_approved = list((await self.session.execute(stmt_sources)).scalars().all())

            # Filter currently valid (not expired)
            valid_sources = [s for s in all_approved if s.is_currently_valid(now)]

            if not valid_sources:
                status = ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE
                explanation = (
                    "No currently valid, approved authoritative evidence sources exist in this workspace "
                    "to substantiate or evaluate this factual claim. Note: absence of evidence is never treated as proof of falsity."
                )
                uncertainty = 1.0
                supporting_snapshots = []
                contradicting_snapshots = []
            else:
                supporting: list[tuple[EvidenceSource, str]] = []
                contradicting: list[tuple[EvidenceSource, str]] = []

                for src in valid_sources:
                    is_sup, is_con, excerpt = _evaluate_source_match(claim.claim_text, src)
                    if is_con:
                        contradicting.append((src, excerpt or ""))
                    elif is_sup:
                        supporting.append((src, excerpt or ""))

                supporting_snapshots = [
                    {
                        "source_id": str(s.id),
                        "title": s.title,
                        "version": s.version,
                        "source_type": s.source_type.value,
                        "matched_excerpt": exc,
                    }
                    for s, exc in supporting
                ]
                contradicting_snapshots = [
                    {
                        "source_id": str(s.id),
                        "title": s.title,
                        "version": s.version,
                        "source_type": s.source_type.value,
                        "matched_excerpt": exc,
                    }
                    for s, exc in contradicting
                ]

                if supporting and contradicting:
                    status = ClaimAssessmentStatus.CONFLICTING_EVIDENCE
                    explanation = (
                        f"Credible approved sources provide conflicting evidence for this claim: "
                        f"{len(supporting)} source(s) support while {len(contradicting)} source(s) contradict."
                    )
                    uncertainty = 0.7

                elif supporting and not contradicting:
                    status = ClaimAssessmentStatus.SUPPORTED
                    titles = ", ".join(f"'{s.title}' (v{s.version})" for s, _ in supporting)
                    explanation = f"Claim is directly supported by approved authoritative evidence source(s): {titles}."
                    uncertainty = 0.05

                elif contradicting and not supporting:
                    status = ClaimAssessmentStatus.CONTRADICTED
                    titles = ", ".join(f"'{s.title}' (v{s.version})" for s, _ in contradicting)
                    explanation = f"Claim is directly contradicted by approved authoritative evidence source(s): {titles}."
                    uncertainty = 0.05

                else:
                    status = ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE
                    explanation = (
                        "No adequate evidence was found in currently approved sources to verify or dispute this claim. "
                        "Note: absence of evidence is never treated as proof of falsity."
                    )
                    uncertainty = 1.0

        assessment = ClaimAssessment(
            claim_id=claim.id,
            revision_id=revision.id,
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_version=policy_version,
            assessment_status=status,
            explanation=explanation,
            uncertainty_score=uncertainty,
            engine_version=ENGINE_VERSION,
            assessed_by_id=actor_id,
            assessed_at=now,
            supporting_sources_snapshot=supporting_snapshots,
            contradicting_sources_snapshot=contradicting_snapshots,
        )
        self.session.add(assessment)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CLAIM_ASSESSED,
            actor_id=actor_id,
            resource_type="ClaimAssessment",
            resource_id=str(assessment.id),
            workspace_id=workspace_id,
            event_payload={
                "claim_id": str(claim.id),
                "assessment_status": assessment.assessment_status.value,
                "uncertainty_score": assessment.uncertainty_score,
                "supporting_count": len(supporting_snapshots),
                "contradicting_count": len(contradicting_snapshots),
            },
        )
        return assessment

    async def list_claim_assessments(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ClaimAssessment], int]:
        """List historical assessments for a specific claim in chronological order."""
        # Ensure claim exists in revision and workspace
        await self.get_claim(workspace_id, submission_id, revision_number, claim_id)

        filters = [
            ClaimAssessment.claim_id == claim_id,
            ClaimAssessment.workspace_id == workspace_id,
        ]
        count_stmt = select(func.count(ClaimAssessment.id)).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(ClaimAssessment)
            .where(*filters)
            .order_by(ClaimAssessment.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        assessments = list((await self.session.execute(stmt)).scalars().all())
        return assessments, total

    async def get_claim_assessment(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        claim_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> ClaimAssessment:
        """Retrieve a specific claim assessment."""
        await self.get_claim(workspace_id, submission_id, revision_number, claim_id)
        stmt = select(ClaimAssessment).where(
            ClaimAssessment.id == assessment_id,
            ClaimAssessment.claim_id == claim_id,
            ClaimAssessment.workspace_id == workspace_id,
        )
        assessment = (await self.session.execute(stmt)).scalar_one_or_none()
        if assessment is None:
            raise NotFoundError("ClaimAssessment", str(assessment_id))
        return assessment
