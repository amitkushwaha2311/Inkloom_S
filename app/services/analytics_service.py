"""Inkloom Sentinel - Provenance & Governance Analytics Service.

Provides:
- Submission provenance assembly across revisions, deterministic verifications,
  claims, semantic checks, corrections, and human review decisions.
- Workspace governance analytics: violation counts, guideline rankings,
  turnaround duration, intervention percentages, and chronological trend aggregation.
"""

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domain.enums import (
    CorrectionStatus,
    FindingCategory,
    ReviewDecisionType,
    SemanticOutcome,
    SeverityLevel,
    SubmissionStatus,
)
from app.domain.models.evidence import ContentClaim
from app.domain.models.policy import PolicyGuideline
from app.domain.models.review import CorrectionSuggestion, ReviewDecision
from app.domain.models.semantic import SemanticReviewFinding, SemanticReviewRun
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.domain.models.verification import VerificationFinding, VerificationRun
from app.domain.schemas.audit import (
    CategoryViolationMetric,
    ClaimAssessmentProvenance,
    ClaimsProvenance,
    CorrectionAcceptanceMetric,
    CorrectionSuggestionProvenance,
    DeterministicProvenance,
    GovernanceAnalyticsResponse,
    GuidelineViolationMetric,
    HumanInterventionMetric,
    ReviewDecisionProvenance,
    RevisionProvenanceItem,
    SemanticFindingProvenance,
    SemanticReviewProvenance,
    SeverityViolationMetric,
    SubmissionProvenanceResponse,
    TimelineTrendPoint,
    TurnaroundTimeMetric,
    VerificationFindingProvenance,
)

logger = get_logger(__name__)


class AnalyticsService:
    """Service governing submission provenance retrieval and workspace governance analytics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_submission_provenance(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
    ) -> SubmissionProvenanceResponse:
        """Assemble an authoritative, read-only lifecycle provenance of a content submission.

        Distinguishes missing historical runs from verified clean outcomes.
        """
        # 1. Fetch submission ensuring workspace isolation
        stmt = select(ContentSubmission).where(
            ContentSubmission.id == submission_id,
            ContentSubmission.workspace_id == workspace_id,
        )
        sub_res = await self.session.execute(stmt)
        submission = sub_res.scalar_one_or_none()
        if not submission:
            raise NotFoundError("ContentSubmission", submission_id)

        # 2. Load all revisions ordered chronologically
        rev_stmt = (
            select(ContentRevision)
            .where(ContentRevision.submission_id == submission_id)
            .order_by(ContentRevision.revision_number.asc())
        )
        rev_res = await self.session.execute(rev_stmt)
        revisions = rev_res.scalars().all()

        # 3. Assemble provenance for each revision
        revision_items: list[RevisionProvenanceItem] = []
        all_policies_used: set[tuple[str, int]] = set()
        all_decisions_count = 0
        latest_decision_str: str | None = None

        for rev in revisions:
            meta = rev.metadata_payload or {}
            content_hash = meta.get("content_hash")
            change_summary = meta.get("change_summary")
            created_by_id = meta.get("created_by_id")

            # Check if applied from suggestion
            sug_stmt = select(CorrectionSuggestion.id).where(
                CorrectionSuggestion.applied_revision_id == rev.id
            )
            sug_res = await self.session.execute(sug_stmt)
            applied_sug_id = sug_res.scalar_one_or_none()

            # Deterministic verification runs & findings
            vrun_stmt = (
                select(VerificationRun)
                .where(VerificationRun.revision_id == rev.id)
                .order_by(VerificationRun.created_at.desc())
            )
            vruns = (await self.session.execute(vrun_stmt)).scalars().all()

            if not vruns:
                det_prov = DeterministicProvenance(
                    status="not_run",
                    total_rules=0,
                    passed_rules=0,
                    violation_count=0,
                    findings=[],
                )
            else:
                latest_vrun = vruns[0]
                all_policies_used.add((str(latest_vrun.policy_id), latest_vrun.policy_version))

                findings_stmt = select(VerificationFinding).where(
                    VerificationFinding.revision_id == rev.id
                )
                f_objs = (await self.session.execute(findings_stmt)).scalars().all()

                findings_list = [
                    VerificationFindingProvenance(
                        id=f.id,
                        guideline_id=f.guideline_id,
                        category=f.category,
                        severity=f.severity,
                        message=f.message,
                        flagged_excerpt=f.flagged_excerpt,
                        char_start=f.char_start,
                        char_end=f.char_end,
                        recommendation=f.recommendation,
                        evidence_references=[
                            {
                                "reference_type": er.reference_type.value,
                                "source_identifier": er.source_identifier,
                                "source_url": er.source_url,
                                "excerpt_quote": er.excerpt_quote,
                                "confidence_score": er.confidence_score,
                            }
                            for er in (f.evidence_references or [])
                        ],
                    )
                    for f in f_objs
                ]

                det_status = (
                    "verified_clean" if latest_vrun.violation_count == 0 else "violations_found"
                )
                det_prov = DeterministicProvenance(
                    status=det_status,
                    run_id=latest_vrun.id,
                    policy_id=latest_vrun.policy_id,
                    policy_version=latest_vrun.policy_version,
                    total_rules=latest_vrun.total_rules,
                    passed_rules=latest_vrun.passed_rules,
                    violation_count=latest_vrun.violation_count,
                    executed_by_id=latest_vrun.executed_by_id,
                    executed_at=latest_vrun.created_at,
                    findings=findings_list,
                )

            # Claims and assessments
            claims_stmt = (
                select(ContentClaim)
                .where(ContentClaim.revision_id == rev.id)
                .order_by(ContentClaim.created_at.asc())
            )
            claims = (await self.session.execute(claims_stmt)).scalars().all()

            if not claims:
                claim_prov = ClaimsProvenance(
                    status="no_claims_discovered",
                    total_claims=0,
                    claims=[],
                )
            else:
                claim_items: list[ClaimAssessmentProvenance] = []
                has_any_assessment = False
                for cl in claims:
                    assessments = cl.assessments or []
                    if assessments:
                        has_any_assessment = True
                        top_a = assessments[0]
                        if top_a.policy_id and top_a.policy_version:
                            all_policies_used.add((str(top_a.policy_id), top_a.policy_version))
                        claim_items.append(
                            ClaimAssessmentProvenance(
                                claim_id=cl.id,
                                claim_text=cl.claim_text,
                                claim_type=cl.claim_type.value,
                                discovery_status=cl.discovery_status.value,
                                char_start=cl.char_start,
                                char_end=cl.char_end,
                                assessment_status=top_a.assessment_status.value,
                                explanation=top_a.explanation,
                                uncertainty_score=top_a.uncertainty_score,
                                supporting_sources=top_a.supporting_sources_snapshot or [],
                                contradicting_sources=top_a.contradicting_sources_snapshot or [],
                            )
                        )
                    else:
                        claim_items.append(
                            ClaimAssessmentProvenance(
                                claim_id=cl.id,
                                claim_text=cl.claim_text,
                                claim_type=cl.claim_type.value,
                                discovery_status=cl.discovery_status.value,
                                char_start=cl.char_start,
                                char_end=cl.char_end,
                                assessment_status=None,
                                explanation=None,
                                uncertainty_score=None,
                            )
                        )

                claim_prov = ClaimsProvenance(
                    status="assessed" if has_any_assessment else "not_assessed",
                    total_claims=len(claims),
                    claims=claim_items,
                )

            # Semantic review runs & findings
            srun_stmt = (
                select(SemanticReviewRun)
                .where(SemanticReviewRun.revision_id == rev.id)
                .order_by(SemanticReviewRun.created_at.desc())
            )
            sruns = (await self.session.execute(srun_stmt)).scalars().all()

            if not sruns:
                sem_prov = SemanticReviewProvenance(
                    status="not_run",
                    violation_count=0,
                    needs_review_count=0,
                    findings=[],
                )
            else:
                latest_srun = sruns[0]
                all_policies_used.add((str(latest_srun.policy_id), latest_srun.policy_version))

                sem_findings_stmt = select(SemanticReviewFinding).where(
                    SemanticReviewFinding.run_id == latest_srun.id
                )
                sf_objs = (await self.session.execute(sem_findings_stmt)).scalars().all()

                sf_list = [
                    SemanticFindingProvenance(
                        id=sf.id,
                        guideline_id=sf.guideline_id,
                        category=sf.category,
                        outcome=sf.outcome.value,
                        explanation=sf.explanation,
                        flagged_excerpt=sf.flagged_excerpt,
                        char_start=sf.char_start,
                        char_end=sf.char_end,
                        confidence_score=sf.confidence_score,
                        uncertainty_reason=sf.uncertainty_reason,
                        recommendation=sf.recommendation,
                    )
                    for sf in sf_objs
                ]

                sem_status = (
                    "verified_clean"
                    if latest_srun.overall_outcome == SemanticOutcome.PASS
                    else "issues_flagged"
                )
                sem_prov = SemanticReviewProvenance(
                    status=sem_status,
                    run_id=latest_srun.id,
                    policy_id=latest_srun.policy_id,
                    policy_version=latest_srun.policy_version,
                    overall_outcome=latest_srun.overall_outcome.value,
                    violation_count=latest_srun.violation_count,
                    needs_review_count=latest_srun.needs_review_count,
                    engine_version=latest_srun.engine_version,
                    executed_at=latest_srun.created_at,
                    findings=sf_list,
                )

            # Correction suggestions
            csug_stmt = select(CorrectionSuggestion).where(
                CorrectionSuggestion.revision_id == rev.id
            )
            csugs = (await self.session.execute(csug_stmt)).scalars().all()
            csug_list = [
                CorrectionSuggestionProvenance(
                    id=s.id,
                    original_text=s.original_text,
                    proposed_replacement=s.proposed_replacement,
                    recommended_action=s.recommended_action,
                    reason=s.reason,
                    status=s.status.value,
                    created_by_id=s.created_by_id,
                    reviewed_by_id=s.reviewed_by_id,
                    applied_revision_id=s.applied_revision_id,
                    created_at=s.created_at,
                )
                for s in csugs
            ]

            # Review decisions
            dec_stmt = (
                select(ReviewDecision)
                .where(ReviewDecision.revision_id == rev.id)
                .order_by(ReviewDecision.decided_at.asc())
            )
            decs = (await self.session.execute(dec_stmt)).scalars().all()
            all_decisions_count += len(decs)
            dec_list = []
            for d in decs:
                latest_decision_str = d.decision.value
                if d.policy_id and d.policy_version:
                    all_policies_used.add((str(d.policy_id), d.policy_version))
                dec_list.append(
                    ReviewDecisionProvenance(
                        id=d.id,
                        decision=d.decision.value,
                        reviewer_id=d.reviewer_id,
                        rationale_summary=d.rationale_summary,
                        feedback_notes=d.feedback_notes,
                        policy_id=d.policy_id,
                        policy_version=d.policy_version,
                        decided_at=d.decided_at,
                    )
                )

            revision_items.append(
                RevisionProvenanceItem(
                    revision_id=rev.id,
                    revision_number=rev.revision_number,
                    content_format=rev.content_format,
                    content_hash=content_hash,
                    content_length=len(rev.content_text),
                    change_summary=change_summary,
                    source_metadata=rev.metadata_payload.get("source_metadata"),
                    submitted_at=rev.submitted_at,
                    created_by_id=created_by_id,
                    was_applied_from_suggestion_id=applied_sug_id,
                    deterministic_verification=det_prov,
                    claims_verification=claim_prov,
                    semantic_review=sem_prov,
                    correction_suggestions=csug_list,
                    review_decisions=dec_list,
                )
            )

        lifecycle_summary = {
            "policy_versions_evaluated": [
                {"policy_id": p_id, "policy_version": p_ver}
                for p_id, p_ver in sorted(all_policies_used)
            ],
            "total_decisions_rendered": all_decisions_count,
            "latest_decision": latest_decision_str,
            "is_currently_approved": submission.status == SubmissionStatus.APPROVED,
        }

        return SubmissionProvenanceResponse(
            submission_id=submission.id,
            workspace_id=submission.workspace_id,
            title=submission.title,
            campaign_tag=submission.campaign_tag,
            current_status=submission.status,
            author_id=submission.author_id,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
            total_revisions=len(revision_items),
            revisions=revision_items,
            lifecycle_summary=lifecycle_summary,
        )

    async def get_governance_analytics(
        self,
        workspace_id: uuid.UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> GovernanceAnalyticsResponse:
        """Calculate workspace-scoped governance metrics, rankings, turnaround times, and trends."""
        # 1. Total Submissions & Revisions
        sub_query = select(ContentSubmission).where(ContentSubmission.workspace_id == workspace_id)
        if start_date:
            sub_query = sub_query.where(ContentSubmission.created_at >= start_date)
        if end_date:
            sub_query = sub_query.where(ContentSubmission.created_at <= end_date)
        subs = (await self.session.execute(sub_query)).scalars().all()
        total_submissions = len(subs)

        sub_ids = [s.id for s in subs]
        if not sub_ids:
            # Short-circuit empty dataset cleanly
            return self._build_empty_analytics(workspace_id, start_date, end_date)

        rev_query = select(ContentRevision).where(ContentRevision.submission_id.in_(sub_ids))
        if start_date:
            rev_query = rev_query.where(ContentRevision.submitted_at >= start_date)
        if end_date:
            rev_query = rev_query.where(ContentRevision.submitted_at <= end_date)
        revs = (await self.session.execute(rev_query)).scalars().all()
        total_revisions = len(revs)
        rev_id_to_rev = {r.id: r for r in revs}

        # 2. Review Decisions & Turnaround Duration
        dec_query = select(ReviewDecision).where(ReviewDecision.submission_id.in_(sub_ids))
        if start_date:
            dec_query = dec_query.where(ReviewDecision.decided_at >= start_date)
        if end_date:
            dec_query = dec_query.where(ReviewDecision.decided_at <= end_date)
        decisions = (await self.session.execute(dec_query)).scalars().all()

        total_reviews_completed = len(decisions)
        interventions = [
            d
            for d in decisions
            if d.decision in (ReviewDecisionType.REQUEST_CHANGES, ReviewDecisionType.REJECT)
        ]
        intervention_count = len(interventions)
        intervention_rate = (
            (intervention_count / total_reviews_completed * 100.0)
            if total_reviews_completed > 0
            else 0.0
        )

        human_intervention = HumanInterventionMetric(
            total_reviews_completed=total_reviews_completed,
            reviews_requiring_intervention=intervention_count,
            intervention_rate_percentage=round(intervention_rate, 2),
        )

        # Calculate turnaround durations in hours
        turnaround_hours: list[float] = []
        for d in decisions:
            rev = rev_id_to_rev.get(d.revision_id)
            if rev and rev.submitted_at:
                delta = (d.decided_at - rev.submitted_at).total_seconds() / 3600.0
                if delta >= 0:
                    turnaround_hours.append(delta)

        if turnaround_hours:
            turnaround_metric = TurnaroundTimeMetric(
                total_decisions_measured=len(turnaround_hours),
                average_hours=round(statistics.mean(turnaround_hours), 2),
                median_hours=round(statistics.median(turnaround_hours), 2),
                min_hours=round(min(turnaround_hours), 2),
                max_hours=round(max(turnaround_hours), 2),
            )
        else:
            turnaround_metric = TurnaroundTimeMetric(
                total_decisions_measured=0,
                average_hours=None,
                median_hours=None,
                min_hours=None,
                max_hours=None,
            )

        # 3. Correction Suggestion Acceptance Rates
        sug_query = select(CorrectionSuggestion).where(
            CorrectionSuggestion.workspace_id == workspace_id
        )
        if start_date:
            sug_query = sug_query.where(CorrectionSuggestion.created_at >= start_date)
        if end_date:
            sug_query = sug_query.where(CorrectionSuggestion.created_at <= end_date)
        suggestions = (await self.session.execute(sug_query)).scalars().all()

        total_sug = len(suggestions)
        accepted_sug = sum(1 for s in suggestions if s.status == CorrectionStatus.ACCEPTED)
        rejected_sug = sum(1 for s in suggestions if s.status == CorrectionStatus.REJECTED)
        proposed_sug = sum(1 for s in suggestions if s.status == CorrectionStatus.PROPOSED)
        acceptance_rate = (accepted_sug / total_sug * 100.0) if total_sug > 0 else 0.0

        correction_acceptance = CorrectionAcceptanceMetric(
            total_suggestions=total_sug,
            accepted_count=accepted_sug,
            rejected_count=rejected_sug,
            proposed_count=proposed_sug,
            acceptance_rate_percentage=round(acceptance_rate, 2),
        )

        # 4. Violations by Category & Severity, and Most Frequent Guidelines
        cat_counts: dict[FindingCategory, int] = defaultdict(int)
        sev_counts: dict[SeverityLevel, int] = defaultdict(int)
        guideline_violation_counts: dict[uuid.UUID, int] = defaultdict(int)

        # Deterministic findings
        if rev_id_to_rev:
            det_f_query = select(VerificationFinding).where(
                VerificationFinding.revision_id.in_(list(rev_id_to_rev.keys()))
            )
            det_findings = (await self.session.execute(det_f_query)).scalars().all()
            for df in det_findings:
                cat_counts[df.category] += 1
                sev_counts[df.severity] += 1
                if df.guideline_id:
                    guideline_violation_counts[df.guideline_id] += 1

        # Semantic findings where outcome == VIOLATION
        sem_run_query = select(SemanticReviewRun).where(
            SemanticReviewRun.workspace_id == workspace_id
        )
        if start_date:
            sem_run_query = sem_run_query.where(SemanticReviewRun.created_at >= start_date)
        if end_date:
            sem_run_query = sem_run_query.where(SemanticReviewRun.created_at <= end_date)
        sem_runs = (await self.session.execute(sem_run_query)).scalars().all()
        sem_run_ids = [sr.id for sr in sem_runs]

        if sem_run_ids:
            sem_f_query = select(SemanticReviewFinding).where(
                SemanticReviewFinding.run_id.in_(sem_run_ids),
                SemanticReviewFinding.outcome == SemanticOutcome.VIOLATION,
            )
            sem_findings = (await self.session.execute(sem_f_query)).scalars().all()
            for sf in sem_findings:
                cat_counts[sf.category] += 1
                if sf.guideline_id:
                    guideline_violation_counts[sf.guideline_id] += 1

        # Format category metrics
        violations_by_category = [
            CategoryViolationMetric(category=cat, count=cnt)
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Format severity metrics
        violations_by_severity = [
            SeverityViolationMetric(severity=sev, count=cnt)
            for sev, cnt in sorted(sev_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Resolve guideline titles for top violated guidelines
        most_frequent_guidelines: list[GuidelineViolationMetric] = []
        if guideline_violation_counts:
            sorted_guidelines = sorted(
                guideline_violation_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
            g_ids = [g_id for g_id, _ in sorted_guidelines]
            g_objs = (
                (
                    await self.session.execute(
                        select(PolicyGuideline).where(PolicyGuideline.id.in_(g_ids))
                    )
                )
                .scalars()
                .all()
            )
            g_map = {g.id: g for g in g_objs}

            for g_id, cnt in sorted_guidelines:
                g_obj = g_map.get(g_id)
                most_frequent_guidelines.append(
                    GuidelineViolationMetric(
                        guideline_id=g_id,
                        guideline_title=g_obj.title if g_obj else None,
                        category=g_obj.category.value if g_obj else "unknown",
                        violation_count=cnt,
                    )
                )

        # 5. Historical Trends
        daily_submissions: dict[str, int] = defaultdict(int)
        daily_revisions: dict[str, int] = defaultdict(int)
        daily_reviews: dict[str, int] = defaultdict(int)
        daily_violations: dict[str, int] = defaultdict(int)

        for s in subs:
            day_str = s.created_at.strftime("%Y-%m-%d")
            daily_submissions[day_str] += 1

        for r in revs:
            day_str = r.submitted_at.strftime("%Y-%m-%d")
            daily_revisions[day_str] += 1

        for d in decisions:
            day_str = d.decided_at.strftime("%Y-%m-%d")
            daily_reviews[day_str] += 1

        if rev_id_to_rev:
            for df in det_findings:
                day_str = df.created_at.strftime("%Y-%m-%d")
                daily_violations[day_str] += 1
        if sem_run_ids:
            for sf in sem_findings:
                day_str = sf.created_at.strftime("%Y-%m-%d")
                daily_violations[day_str] += 1

        all_days = sorted(
            set(daily_submissions.keys())
            | set(daily_revisions.keys())
            | set(daily_reviews.keys())
            | set(daily_violations.keys())
        )

        trends: list[TimelineTrendPoint] = [
            TimelineTrendPoint(
                date=day,
                submissions_count=daily_submissions.get(day, 0),
                revisions_count=daily_revisions.get(day, 0),
                reviews_completed=daily_reviews.get(day, 0),
                violations_flagged=daily_violations.get(day, 0),
            )
            for day in all_days
        ]

        return GovernanceAnalyticsResponse(
            workspace_id=workspace_id,
            time_window_start=start_date,
            time_window_end=end_date,
            total_submissions=total_submissions,
            total_revisions=total_revisions,
            total_reviews_completed=total_reviews_completed,
            violations_by_category=violations_by_category,
            violations_by_severity=violations_by_severity,
            most_frequent_guideline_violations=most_frequent_guidelines,
            human_intervention=human_intervention,
            correction_acceptance=correction_acceptance,
            turnaround_time=turnaround_metric,
            historical_trends=trends,
            generated_at=datetime.now(UTC),
        )

    def _build_empty_analytics(
        self,
        workspace_id: uuid.UUID,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> GovernanceAnalyticsResponse:
        """Return a gracefully initialized response for an empty dataset."""
        return GovernanceAnalyticsResponse(
            workspace_id=workspace_id,
            time_window_start=start_date,
            time_window_end=end_date,
            total_submissions=0,
            total_revisions=0,
            total_reviews_completed=0,
            violations_by_category=[],
            violations_by_severity=[],
            most_frequent_guideline_violations=[],
            human_intervention=HumanInterventionMetric(
                total_reviews_completed=0,
                reviews_requiring_intervention=0,
                intervention_rate_percentage=0.0,
            ),
            correction_acceptance=CorrectionAcceptanceMetric(
                total_suggestions=0,
                accepted_count=0,
                rejected_count=0,
                proposed_count=0,
                acceptance_rate_percentage=0.0,
            ),
            turnaround_time=TurnaroundTimeMetric(
                total_decisions_measured=0,
                average_hours=None,
                median_hours=None,
                min_hours=None,
                max_hours=None,
            ),
            historical_trends=[],
            generated_at=datetime.now(UTC),
        )
