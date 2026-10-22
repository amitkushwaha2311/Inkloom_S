"""Inkloom Sentinel - Unified Review & Correction Workflow Service.

Orchestrates:
- Unified review summary assembling deterministic checks, evidence claims, and semantic findings.
- Structured correction suggestions with provenance and evidence bindings.
- Concurrency-safe application of corrections generating new revisions via SubmissionService.
- Human review governance with separation of duties enforcement.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    ClaimAssessmentStatus,
    CorrectionStatus,
    PolicyStatus,
    ReviewDecisionType,
    SemanticOutcome,
    SourceApprovalStatus,
    SubmissionStatus,
    UnifiedCheckStatus,
    UnifiedReviewOutcome,
)
from app.domain.models.evidence import ContentClaim, EvidenceSource
from app.domain.models.policy import BrandPolicy
from app.domain.models.review import CorrectionSuggestion, ReviewDecision
from app.domain.models.semantic import SemanticReviewRun
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.domain.models.verification import VerificationFinding, VerificationRun
from app.domain.schemas.review import (
    CheckExecutionSummary,
    CorrectionSuggestionCreate,
    CorrectionSuggestionResponse,
    CorrectionSuggestionUpdate,
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    UnifiedReviewSummaryResponse,
)
from app.domain.schemas.submission import ContentRevisionCreate
from app.services.audit_service import AuditService
from app.services.submission_service import SubmissionService

logger = get_logger(__name__)


class ReviewService:
    """Orchestration service for unified reviews, correction suggestions, and governance decisions."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        submission_service: SubmissionService,
    ) -> None:
        self.session = session
        self.audit = audit
        self.submission_service = submission_service

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _require_revision(
        self, submission_id: uuid.UUID, workspace_id: uuid.UUID, revision_number: int
    ) -> ContentRevision:
        """Load a ContentRevision and confirm its submission belongs to workspace."""
        stmt = (
            select(ContentRevision)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(
                ContentRevision.submission_id == submission_id,
                ContentRevision.revision_number == revision_number,
                ContentSubmission.workspace_id == workspace_id,
            )
            .options(selectinload(ContentRevision.submission))
        )
        revision = (await self.session.execute(stmt)).scalar_one_or_none()
        if revision is None:
            raise NotFoundError(
                "ContentRevision",
                f"submission={submission_id} revision={revision_number}",
            )
        return revision

    # ------------------------------------------------------------------
    # 1. Unified Review Orchestration Summary
    # ------------------------------------------------------------------

    async def get_unified_review_summary(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        policy_id: uuid.UUID,
    ) -> UnifiedReviewSummaryResponse:
        """Assemble comprehensive compliance findings across all engines for a revision and active policy."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        # 1. Validate active policy
        stmt_policy = select(BrandPolicy).where(
            BrandPolicy.id == policy_id,
            BrandPolicy.workspace_id == workspace_id,
        )
        policy = (await self.session.execute(stmt_policy)).scalar_one_or_none()
        if policy is None:
            raise NotFoundError("BrandPolicy", str(policy_id))
        if policy.status != PolicyStatus.ACTIVE:
            raise ValidationError(
                f"Policy '{policy.name}' (v{policy.version}) has status '{policy.status.value}'. "
                f"Unified review summary requires an ACTIVE policy."
            )

        now = datetime.now(UTC)
        checks: dict[str, CheckExecutionSummary] = {}
        unresolved_count = 0

        # 2. Deterministic Verification Run
        stmt_verif = (
            select(VerificationRun)
            .where(
                VerificationRun.revision_id == revision.id,
                VerificationRun.policy_id == policy.id,
            )
            .order_by(VerificationRun.created_at.desc())
        )
        verif_run = (await self.session.execute(stmt_verif)).scalars().first()

        deterministic_findings_data: list[dict] = []
        if verif_run is not None:
            # Load findings
            stmt_f = (
                select(VerificationFinding)
                .where(VerificationFinding.run_id == verif_run.id)
                .options(selectinload(VerificationFinding.guideline))
            )
            findings = list((await self.session.execute(stmt_f)).scalars().all())
            deterministic_findings_data = [
                {
                    "id": str(f.id),
                    "guideline_id": str(f.guideline_id) if f.guideline_id else None,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "message": f.message,
                    "flagged_excerpt": f.flagged_excerpt,
                    "char_start": f.char_start,
                    "char_end": f.char_end,
                    "recommendation": f.recommendation,
                    "rule_type": (
                        (f.guideline.rule_config or {}).get("rule_type")
                        if "guideline" in f.__dict__ and f.guideline is not None
                        else None
                    ),
                }
                for f in findings
            ]
            unresolved_count += len(findings)
            outcome_str = "violation" if verif_run.violation_count > 0 else "pass"
            checks["deterministic"] = CheckExecutionSummary(
                name="deterministic_verification",
                status=UnifiedCheckStatus.COMPLETED,
                outcome=outcome_str,
                run_id=verif_run.id,
                engine_version="sentinel-deterministic-v1.0",
                execution_timestamp=verif_run.created_at,
                finding_count=len(findings),
                message=f"Deterministic engine evaluated {verif_run.total_rules} rule(s).",
            )
        else:
            checks["deterministic"] = CheckExecutionSummary(
                name="deterministic_verification",
                status=UnifiedCheckStatus.NOT_RUN,
                message="Deterministic verification check has not been executed on this revision against this policy.",
            )

        # 3. Evidence Claim Assessments
        stmt_claims = (
            select(ContentClaim)
            .where(
                ContentClaim.revision_id == revision.id,
                ContentClaim.workspace_id == workspace_id,
            )
            .options(selectinload(ContentClaim.assessments))
        )
        claims = list((await self.session.execute(stmt_claims)).scalars().all())

        claim_assessments_data: list[dict] = []
        claims_not_assessed = 0
        claims_contradicted = 0
        claims_insufficient = 0
        claims_needs_review = 0

        for c in claims:
            latest_assessment = c.assessments[0] if c.assessments else None
            if latest_assessment is None:
                claims_not_assessed += 1
                claim_assessments_data.append(
                    {
                        "claim_id": str(c.id),
                        "claim_text": c.claim_text,
                        "claim_type": c.claim_type.value,
                        "discovery_status": c.discovery_status.value,
                        "assessment_status": "unassessed",
                        "explanation": "Claim has not been verified against approved evidence sources.",
                    }
                )
            else:
                status_val = latest_assessment.assessment_status
                if status_val == ClaimAssessmentStatus.CONTRADICTED:
                    claims_contradicted += 1
                    unresolved_count += 1
                elif status_val == ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE:
                    claims_insufficient += 1
                    unresolved_count += 1
                elif status_val in (
                    ClaimAssessmentStatus.NEEDS_HUMAN_REVIEW,
                    ClaimAssessmentStatus.CONFLICTING_EVIDENCE,
                ):
                    claims_needs_review += 1
                    unresolved_count += 1

                claim_assessments_data.append(
                    {
                        "claim_id": str(c.id),
                        "claim_text": c.claim_text,
                        "claim_type": c.claim_type.value,
                        "discovery_status": c.discovery_status.value,
                        "assessment_id": str(latest_assessment.id),
                        "assessment_status": status_val.value,
                        "explanation": latest_assessment.explanation,
                        "uncertainty_score": latest_assessment.uncertainty_score,
                        "supporting_sources": latest_assessment.supporting_sources_snapshot,
                        "contradicting_sources": latest_assessment.contradicting_sources_snapshot,
                    }
                )

        if not claims:
            checks["claims"] = CheckExecutionSummary(
                name="evidence_claim_assessment",
                status=UnifiedCheckStatus.COMPLETED,
                outcome="pass",
                finding_count=0,
                message="No claims recorded on this revision.",
            )
        elif claims_not_assessed > 0:
            checks["claims"] = CheckExecutionSummary(
                name="evidence_claim_assessment",
                status=UnifiedCheckStatus.NOT_RUN,
                finding_count=len(claims),
                message=f"{claims_not_assessed} claim(s) have not been assessed against approved evidence.",
            )
        else:
            claim_outcome = (
                "violation"
                if claims_contradicted > 0
                else (
                    "needs_review"
                    if (claims_insufficient > 0 or claims_needs_review > 0)
                    else "pass"
                )
            )
            checks["claims"] = CheckExecutionSummary(
                name="evidence_claim_assessment",
                status=UnifiedCheckStatus.COMPLETED,
                outcome=claim_outcome,
                finding_count=len(claims),
                message=f"{len(claims)} claim(s) assessed against approved evidence sources.",
            )

        # 4. Semantic Review Run
        stmt_sem = (
            select(SemanticReviewRun)
            .where(
                SemanticReviewRun.revision_id == revision.id,
                SemanticReviewRun.policy_id == policy.id,
            )
            .options(selectinload(SemanticReviewRun.findings))
            .order_by(SemanticReviewRun.created_at.desc())
        )
        sem_run = (await self.session.execute(stmt_sem)).scalars().first()

        semantic_findings_data: list[dict] = []
        if sem_run is not None:
            semantic_findings_data = [
                {
                    "id": str(f.id),
                    "guideline_id": str(f.guideline_id) if f.guideline_id else None,
                    "category": f.category.value,
                    "outcome": f.outcome.value,
                    "explanation": f.explanation,
                    "flagged_excerpt": f.flagged_excerpt,
                    "char_start": f.char_start,
                    "char_end": f.char_end,
                    "confidence_score": f.confidence_score,
                    "uncertainty_reason": f.uncertainty_reason,
                    "recommendation": f.recommendation,
                }
                for f in sem_run.findings
            ]
            sem_unresolved = sum(1 for f in sem_run.findings if f.outcome != SemanticOutcome.PASS)
            unresolved_count += sem_unresolved
            checks["semantic"] = CheckExecutionSummary(
                name="semantic_review",
                status=UnifiedCheckStatus.COMPLETED,
                outcome=sem_run.overall_outcome.value,
                run_id=sem_run.id,
                engine_version=sem_run.engine_version,
                execution_timestamp=sem_run.created_at,
                finding_count=len(semantic_findings_data),
                message=f"Semantic engine evaluated guidelines with outcome: {sem_run.overall_outcome.value}.",
            )
        else:
            checks["semantic"] = CheckExecutionSummary(
                name="semantic_review",
                status=UnifiedCheckStatus.NOT_RUN,
                message="Semantic review has not been executed on this revision against this policy.",
            )

        # 5. Load Correction Suggestions
        stmt_sugg = (
            select(CorrectionSuggestion)
            .where(CorrectionSuggestion.revision_id == revision.id)
            .order_by(CorrectionSuggestion.created_at.asc())
        )
        suggestions = list((await self.session.execute(stmt_sugg)).scalars().all())

        # 6. Load Review Decisions
        stmt_dec = (
            select(ReviewDecision)
            .where(ReviewDecision.revision_id == revision.id)
            .order_by(ReviewDecision.created_at.asc())
        )
        decisions = list((await self.session.execute(stmt_dec)).scalars().all())

        # 7. Synthesize Overall Outcome and Clean Pass Determination
        # Rule: Never report an overall clean pass when required checks are missing, failed, or unresolved.
        det_check = checks["deterministic"]
        sem_check = checks["semantic"]
        claims_check = checks["claims"]

        is_incomplete = (
            det_check.status != UnifiedCheckStatus.COMPLETED
            or sem_check.status != UnifiedCheckStatus.COMPLETED
            or claims_check.status != UnifiedCheckStatus.COMPLETED
        )

        has_violations = (
            (verif_run and verif_run.violation_count > 0)
            or (sem_run and sem_run.overall_outcome == SemanticOutcome.VIOLATION)
            or claims_contradicted > 0
        )

        has_inconclusive = sem_run and sem_run.overall_outcome == SemanticOutcome.INCONCLUSIVE

        has_needs_review = (
            (sem_run and sem_run.overall_outcome == SemanticOutcome.NEEDS_REVIEW)
            or claims_insufficient > 0
            or claims_needs_review > 0
        )

        if is_incomplete:
            overall_outcome = UnifiedReviewOutcome.INCOMPLETE
            is_clean_pass = False
        elif has_violations:
            overall_outcome = UnifiedReviewOutcome.ACTION_REQUIRED
            is_clean_pass = False
        elif has_inconclusive:
            overall_outcome = UnifiedReviewOutcome.INCONCLUSIVE
            is_clean_pass = False
        elif has_needs_review:
            overall_outcome = UnifiedReviewOutcome.NEEDS_HUMAN_REVIEW
            is_clean_pass = False
        else:
            overall_outcome = UnifiedReviewOutcome.PASS
            is_clean_pass = True

        return UnifiedReviewSummaryResponse(
            revision_id=revision.id,
            revision_number=revision_number,
            submission_id=submission_id,
            workspace_id=workspace_id,
            policy_id=policy.id,
            policy_version=policy.version,
            policy_name=policy.name,
            overall_outcome=overall_outcome,
            is_clean_pass=is_clean_pass,
            checks=checks,
            deterministic_findings=deterministic_findings_data,
            claim_assessments=claim_assessments_data,
            semantic_findings=semantic_findings_data,
            correction_suggestions=[
                CorrectionSuggestionResponse.model_validate(s) for s in suggestions
            ],
            review_decisions=[ReviewDecisionResponse.model_validate(d) for d in decisions],
            unresolved_issues_count=unresolved_count,
            generated_at=now,
        )

    # ------------------------------------------------------------------
    # 2. Correction Suggestions Management
    # ------------------------------------------------------------------

    async def create_correction_suggestion(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        body: CorrectionSuggestionCreate,
        actor_id: str,
    ) -> CorrectionSuggestion:
        """Create a structured correction suggestion bound to a finding or guideline."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        # Validate evidence source if provided (ensure no fabricated evidence citations)
        if body.evidence_source_id is not None:
            stmt_src = select(EvidenceSource).where(
                EvidenceSource.id == body.evidence_source_id,
                EvidenceSource.workspace_id == workspace_id,
            )
            src = (await self.session.execute(stmt_src)).scalar_one_or_none()
            if src is None:
                raise NotFoundError("EvidenceSource", str(body.evidence_source_id))
            if src.approval_status != SourceApprovalStatus.APPROVED:
                raise ValidationError(
                    f"Evidence source '{src.title}' is '{src.approval_status.value}'. "
                    f"Only APPROVED authoritative sources may be cited for evidence-supported corrections."
                )

        suggestion = CorrectionSuggestion(
            workspace_id=workspace_id,
            submission_id=submission_id,
            revision_id=revision.id,
            finding_id=body.finding_id,
            guideline_id=body.guideline_id,
            original_text=body.original_text,
            char_start=body.char_start,
            char_end=body.char_end,
            proposed_replacement=body.proposed_replacement,
            recommended_action=body.recommended_action,
            reason=body.reason,
            evidence_source_id=body.evidence_source_id,
            evidence_excerpt=body.evidence_excerpt,
            status=CorrectionStatus.PROPOSED,
            created_by_id=actor_id,
        )
        self.session.add(suggestion)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CORRECTION_SUGGESTION_CREATED,
            actor_id=actor_id,
            resource_type="CorrectionSuggestion",
            resource_id=str(suggestion.id),
            workspace_id=workspace_id,
            event_payload={
                "submission_id": str(submission_id),
                "revision_number": revision_number,
                "finding_id": str(body.finding_id) if body.finding_id else None,
                "evidence_source_id": str(body.evidence_source_id)
                if body.evidence_source_id
                else None,
            },
        )
        return suggestion

    async def get_correction_suggestion(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        suggestion_id: uuid.UUID,
    ) -> CorrectionSuggestion:
        """Retrieve an individual correction suggestion."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        stmt = select(CorrectionSuggestion).where(
            CorrectionSuggestion.id == suggestion_id,
            CorrectionSuggestion.revision_id == revision.id,
            CorrectionSuggestion.workspace_id == workspace_id,
        )
        sugg = (await self.session.execute(stmt)).scalar_one_or_none()
        if sugg is None:
            raise NotFoundError("CorrectionSuggestion", str(suggestion_id))
        return sugg

    async def list_correction_suggestions(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
    ) -> list[CorrectionSuggestion]:
        """List all correction suggestions for a content revision."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        stmt = (
            select(CorrectionSuggestion)
            .where(
                CorrectionSuggestion.revision_id == revision.id,
                CorrectionSuggestion.workspace_id == workspace_id,
            )
            .order_by(CorrectionSuggestion.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_correction_suggestion(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        suggestion_id: uuid.UUID,
        body: CorrectionSuggestionUpdate,
        actor_id: str,
    ) -> CorrectionSuggestion:
        """Update suggestion status (accepted/rejected) or refine proposed action."""
        sugg = await self.get_correction_suggestion(
            workspace_id, submission_id, revision_number, suggestion_id
        )

        if body.status is not None:
            sugg.status = body.status
        if body.proposed_replacement is not None:
            sugg.proposed_replacement = body.proposed_replacement
        if body.recommended_action is not None:
            sugg.recommended_action = body.recommended_action
        if body.reason is not None:
            sugg.reason = body.reason

        sugg.reviewed_by_id = actor_id
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CORRECTION_SUGGESTION_UPDATED,
            actor_id=actor_id,
            resource_type="CorrectionSuggestion",
            resource_id=str(sugg.id),
            workspace_id=workspace_id,
            event_payload={
                "status": sugg.status.value,
                "reviewed_by_id": actor_id,
            },
        )
        return sugg

    async def apply_correction_suggestion(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        suggestion_id: uuid.UUID,
        expected_revision_number: int,
        actor_id: str,
    ) -> tuple[CorrectionSuggestion, ContentRevision]:
        """Apply an accepted correction suggestion by creating a new revision.

        Guarantees:
        - Suggestions never mutate ContentRevision records directly.
        - Applies optimistic concurrency verification via SubmissionService.
        - Conflicting suggestions on the prior revision are marked SUPERSEDED.
        """
        sugg = await self.get_correction_suggestion(
            workspace_id, submission_id, revision_number, suggestion_id
        )
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        if sugg.status == CorrectionStatus.REJECTED:
            raise ValidationError("Cannot apply a REJECTED correction suggestion.")
        if sugg.status == CorrectionStatus.SUPERSEDED:
            raise ValidationError("Cannot apply a SUPERSEDED correction suggestion.")
        if sugg.applied_revision_id is not None:
            raise ConflictError("This correction suggestion has already been applied.")
        if sugg.proposed_replacement is None:
            raise ValidationError(
                "Correction suggestion has no proposed replacement text to apply."
            )

        content = revision.content_text
        orig = sugg.original_text
        repl = sugg.proposed_replacement

        # Apply replacement: check character offsets first, fallback to unique substring
        if (
            sugg.char_start is not None
            and sugg.char_end is not None
            and sugg.char_end <= len(content)
            and content[sugg.char_start : sugg.char_end] == orig
        ):
            new_content = content[: sugg.char_start] + repl + content[sugg.char_end :]
        elif orig in content:
            new_content = content.replace(orig, repl, 1)
        else:
            raise ValidationError(
                f"Original text '{orig}' could not be located in revision {revision_number} content."
            )

        # Create new revision through existing SubmissionService with concurrency guard
        rev_create_data = ContentRevisionCreate(
            content_text=new_content,
            content_format=revision.content_format,
            change_summary=f"Applied correction {sugg.id}: {sugg.reason}",
            expected_revision_number=expected_revision_number,
        )
        new_revision = await self.submission_service.create_revision(
            submission_id=submission_id,
            workspace_id=workspace_id,
            data=rev_create_data,
            actor_id=actor_id,
        )

        # Mark suggestion accepted & link applied revision
        sugg.status = CorrectionStatus.ACCEPTED
        sugg.applied_revision_id = new_revision.id
        sugg.reviewed_by_id = actor_id

        # Mark any other suggestions for the same original text on the old revision as SUPERSEDED
        stmt_other = select(CorrectionSuggestion).where(
            CorrectionSuggestion.revision_id == revision.id,
            CorrectionSuggestion.id != sugg.id,
            CorrectionSuggestion.original_text == orig,
            CorrectionSuggestion.status == CorrectionStatus.PROPOSED,
        )
        conflicting = list((await self.session.execute(stmt_other)).scalars().all())
        for c in conflicting:
            c.status = CorrectionStatus.SUPERSEDED

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CORRECTION_APPLIED,
            actor_id=actor_id,
            resource_type="CorrectionSuggestion",
            resource_id=str(sugg.id),
            workspace_id=workspace_id,
            event_payload={
                "submission_id": str(submission_id),
                "source_revision_number": revision_number,
                "new_revision_number": new_revision.revision_number,
                "new_revision_id": str(new_revision.id),
            },
        )

        return sugg, new_revision

    # ------------------------------------------------------------------
    # 3. Human Review Decisions & Separation of Duties
    # ------------------------------------------------------------------

    async def record_review_decision(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        body: ReviewDecisionCreate,
        actor_id: str,
    ) -> ReviewDecision:
        """Record an explicit human governance determination on a content revision.

        Enforces:
        - Separation of duties: Authors cannot approve their own submissions.
        - Submission lifecycle transitions: APPROVED, REJECTED, CHANGES_REQUESTED.
        - Preserves previous decisions immutably in review history.
        """
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        submission = revision.submission

        # Separation of duties: Authors cannot approve their own content
        if actor_id == submission.author_id and body.decision == ReviewDecisionType.APPROVE:
            raise ForbiddenError(
                "Separation of duties violation: Submission authors are not permitted to "
                "approve their own content submissions."
            )

        # Validate policy binding if provided
        policy_version = body.policy_version
        if body.policy_id is not None:
            stmt_policy = select(BrandPolicy).where(
                BrandPolicy.id == body.policy_id,
                BrandPolicy.workspace_id == workspace_id,
            )
            policy = (await self.session.execute(stmt_policy)).scalar_one_or_none()
            if policy is None:
                raise NotFoundError("BrandPolicy", str(body.policy_id))
            if policy.status != PolicyStatus.ACTIVE:
                raise ValidationError(
                    f"Policy '{policy.name}' has status '{policy.status.value}'. "
                    f"Decisions must reference an ACTIVE policy version."
                )
            policy_version = policy.version

        decision_record = ReviewDecision(
            submission_id=submission.id,
            revision_id=revision.id,
            policy_id=body.policy_id,
            policy_version=policy_version,
            review_run_id=body.review_run_id,
            reviewer_id=actor_id,
            decision=body.decision,
            rationale_summary=body.rationale_summary,
            feedback_notes=body.feedback_notes,
            decided_at=datetime.now(UTC),
        )
        self.session.add(decision_record)

        # Transition submission status
        if body.decision == ReviewDecisionType.APPROVE:
            submission.status = SubmissionStatus.APPROVED
        elif body.decision == ReviewDecisionType.REJECT:
            submission.status = SubmissionStatus.REJECTED
        elif body.decision == ReviewDecisionType.REQUEST_CHANGES:
            submission.status = SubmissionStatus.CHANGES_REQUESTED

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.REVIEW_DECIDED,
            actor_id=actor_id,
            resource_type="ReviewDecision",
            resource_id=str(decision_record.id),
            workspace_id=workspace_id,
            event_payload={
                "submission_id": str(submission.id),
                "revision_number": revision_number,
                "decision": decision_record.decision.value,
                "new_submission_status": submission.status.value,
            },
        )

        return decision_record

    async def list_review_decisions(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
    ) -> list[ReviewDecision]:
        """List historical human review determinations for a revision."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        stmt = (
            select(ReviewDecision)
            .where(
                ReviewDecision.revision_id == revision.id,
                ReviewDecision.submission_id == submission_id,
            )
            .order_by(ReviewDecision.decided_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
