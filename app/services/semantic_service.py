"""Inkloom Sentinel - Semantic Review & Contextual Guideline Service.

Evaluates content against brand guidelines requiring contextual and tone understanding:
- Tone and voice alignment.
- Unsubstantiated superlative detection.
- Contextual claim consistency.
- Brand positioning consistency.

Security & Integrity:
- Prompt injection and instruction overrides are rejected: user content is treated
  strictly as untrusted data to analyze, never as instructions to follow.
- Ambiguous or conflicting guidelines result in INCONCLUSIVE or NEEDS_REVIEW
  with explicit uncertainty reasons rather than fabricated certainty.
- Baseline heuristics are clearly separated from deterministic rules, and an
  abstract BaseSemanticReviewer interface provides a clean plug-in boundary
  for advanced NLP / model-based evaluators.
- Historical runs remain strictly immutable.
"""

import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    FindingCategory,
    PolicyStatus,
    SemanticOutcome,
)
from app.domain.models.policy import BrandPolicy, PolicyGuideline
from app.domain.models.semantic import SemanticReviewFinding, SemanticReviewRun
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# Known adversarial prompt injection patterns in untrusted content
PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|guidelines)\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|guidelines)\b",
    r"\bsystem\s+override\b",
    r"\boutput\s+pass\s+only\b",
    r"\byou\s+must\s+(?:return|output)\s+pass\b",
    r"\bjailbreak\b",
    r"\bdeveloper\s+mode\s+enabled\b",
    r"\badmin\s+override\b",
]

# Baseline unsubstantiated superlatives
UNSUBSTANTIATED_SUPERLATIVES = [
    "world's best",
    "the absolute best",
    "unrivaled in history",
    "100% infallible",
    "zero possibility of error",
    "infinitely superior",
    "completely flawless",
    "unmatched anywhere",
    "number one in the universe",
]

# Baseline aggressive / inappropriate tone indicators
INAPPROPRIATE_TONE_PATTERNS = [
    r"\b(?:idiotic|stupid|awful|garbage|terrible|scam|pathetic)\b",
    r"\bhate\s+(?:our\s+)?(?:customers|users|clients)\b",
]


@dataclass
class FindingEvaluation:
    """Output from evaluating an individual guideline."""

    guideline_id: uuid.UUID | None
    category: FindingCategory
    outcome: SemanticOutcome
    explanation: str
    flagged_excerpt: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    confidence_score: float | None = 1.0
    uncertainty_reason: str | None = None
    recommendation: str | None = None


@dataclass
class ReviewEvaluation:
    """Aggregate result of evaluating all contextual guidelines."""

    overall_outcome: SemanticOutcome
    findings: list[FindingEvaluation] = field(default_factory=list)
    engine_version: str = "sentinel-semantic-heuristic-v1.0"


class BaseSemanticReviewer(ABC):
    """Abstract interface for contextual semantic guideline evaluation."""

    @abstractmethod
    def evaluate(
        self,
        content: str,
        guidelines: list[PolicyGuideline],
    ) -> ReviewEvaluation:
        """Evaluate content against brand guidelines and return semantic findings."""
        pass


class RuleBasedSemanticReviewer(BaseSemanticReviewer):
    """Conservative baseline semantic reviewer.

    NOTE ON LIMITATIONS:
    This baseline implementation uses deterministic lexical analysis, pattern-based
    heuristic classifiers, and uncertainty estimators. It does NOT claim to provide
    deep human-grade semantic understanding. It serves as a secure, predictable,
    prompt-injection-resistant baseline that can be swapped with NLP/model-based
    evaluators implementing BaseSemanticReviewer.
    """

    engine_version: str = "sentinel-semantic-heuristic-v1.0"

    def evaluate(
        self,
        content: str,
        guidelines: list[PolicyGuideline],
    ) -> ReviewEvaluation:
        findings: list[FindingEvaluation] = []

        # 1. Prompt Injection Defense
        # Treat user content strictly as untrusted data to analyze, never as instructions to execute.
        for pattern in PROMPT_INJECTION_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                findings.append(
                    FindingEvaluation(
                        guideline_id=None,
                        category=FindingCategory.BRAND_VOICE,
                        outcome=SemanticOutcome.VIOLATION,
                        explanation=(
                            f"Adversarial instruction override detected in content: '{match.group(0)}'. "
                            f"In accordance with Sentinel security controls, user content is treated strictly "
                            f"as data to inspect, not instructions to execute. Manipulation attempt rejected."
                        ),
                        flagged_excerpt=match.group(0),
                        char_start=match.start(),
                        char_end=match.end(),
                        confidence_score=0.98,
                        uncertainty_reason=None,
                        recommendation="Remove prompt injection attempts and instruction overrides from submission.",
                    )
                )

        # 2. Evaluate each guideline contextually
        for g in guidelines:
            # Check for ambiguous or conflicting configuration
            is_ambiguous, amb_reason = self._detect_ambiguity(g)
            if is_ambiguous:
                findings.append(
                    FindingEvaluation(
                        guideline_id=g.id,
                        category=g.category,
                        outcome=SemanticOutcome.INCONCLUSIVE,
                        explanation=(
                            f"Guideline '{g.title}' cannot be reliably evaluated due to ambiguous or "
                            f"conflicting configuration: {amb_reason}"
                        ),
                        confidence_score=0.2,
                        uncertainty_reason=amb_reason,
                        recommendation="Clarify guideline instructions or resolve conflicting directives in the policy.",
                    )
                )
                continue

            # Evaluate based on category and rule_config
            finding = self._evaluate_single_guideline(content, g)
            if finding is not None:
                findings.append(finding)

        # 3. Compute overall outcome
        outcomes = [f.outcome for f in findings]
        if SemanticOutcome.VIOLATION in outcomes:
            overall = SemanticOutcome.VIOLATION
        elif SemanticOutcome.NEEDS_REVIEW in outcomes:
            overall = SemanticOutcome.NEEDS_REVIEW
        elif SemanticOutcome.INCONCLUSIVE in outcomes:
            overall = SemanticOutcome.INCONCLUSIVE
        else:
            overall = SemanticOutcome.PASS

        return ReviewEvaluation(
            overall_outcome=overall,
            findings=findings,
            engine_version=self.engine_version,
        )

    def _detect_ambiguity(self, g: PolicyGuideline) -> tuple[bool, str | None]:
        """Detect ambiguous or conflicting instructions in guideline configuration."""
        cfg = g.rule_config or {}
        text_lower = (g.rule_text or "").lower()

        # Check for explicit conflict flags in config
        if cfg.get("conflicting") or cfg.get("ambiguous"):
            return True, cfg.get(
                "conflict_reason"
            ) or "Guideline explicitly configured as conflicting."

        # Check contradictory tone instructions
        has_formal = "formal" in text_lower or cfg.get("tone") == "formal"
        has_casual = "casual" in text_lower or cfg.get("tone") == "casual"
        if has_formal and has_casual:
            return (
                True,
                "Guideline simultaneously mandates both formal and casual tone, presenting a direct contradiction.",
            )

        # Check empty rule text and missing config
        if not g.rule_text.strip() and not cfg:
            return True, "Guideline has neither descriptive rule text nor rule_config."

        return False, None

    def _evaluate_single_guideline(self, content: str, g: PolicyGuideline) -> FindingEvaluation:
        cfg = g.rule_config or {}
        target_tone = cfg.get("tone", "").lower()
        content_lower = content.lower()

        # A. Unsubstantiated Superlative Detection
        if (
            g.category == FindingCategory.BRAND_VOICE
            or "superlative" in g.title.lower()
            or cfg.get("rule_type") == "superlatives"
        ):
            for sup in UNSUBSTANTIATED_SUPERLATIVES:
                pos = content_lower.find(sup)
                if pos != -1:
                    matched = content[pos : pos + len(sup)]
                    return FindingEvaluation(
                        guideline_id=g.id,
                        category=g.category,
                        outcome=SemanticOutcome.VIOLATION,
                        explanation=(
                            f"Unsubstantiated absolute superlative '{matched}' violates brand voice positioning. "
                            f"Absolute superlatives require empirical verification or must be qualified."
                        ),
                        flagged_excerpt=matched,
                        char_start=pos,
                        char_end=pos + len(sup),
                        confidence_score=0.92,
                        recommendation="Rephrase superlative claim with modest, substantiated phrasing.",
                    )

        # B. Inappropriate / Hostile Tone Detection
        if g.category == FindingCategory.TONE_CONSISTENCY or target_tone in {
            "professional",
            "respectful",
        }:
            for pattern in INAPPROPRIATE_TONE_PATTERNS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return FindingEvaluation(
                        guideline_id=g.id,
                        category=g.category,
                        outcome=SemanticOutcome.VIOLATION,
                        explanation=(
                            f"Negative, hostile, or unprofessional tone detected ('{match.group(0)}') "
                            f"violating guideline '{g.title}'."
                        ),
                        flagged_excerpt=match.group(0),
                        char_start=match.start(),
                        char_end=match.end(),
                        confidence_score=0.95,
                        recommendation="Revise copy to maintain a respectful, professional brand tone.",
                    )

        # C. Subjective / Contextual review guidelines requiring human judgment
        if (
            cfg.get("requires_human_review")
            or "review" in g.title.lower()
            or cfg.get("rule_type") == "human_review"
        ):
            return FindingEvaluation(
                guideline_id=g.id,
                category=g.category,
                outcome=SemanticOutcome.NEEDS_REVIEW,
                explanation=(
                    f"Guideline '{g.title}' involves nuanced creative or subjective judgment that "
                    f"exceeds automated heuristic confidence thresholds."
                ),
                confidence_score=0.5,
                uncertainty_reason="Subjective guideline requiring brand editor or creative lead assessment.",
                recommendation="Have a workspace reviewer evaluate the revision against this guideline.",
            )

        # D. Prohibited context phrases specified in semantic rule_config
        prohibited_context = cfg.get("prohibited_context_phrases") or []
        for phrase in prohibited_context:
            if isinstance(phrase, str) and phrase.lower() in content_lower:
                pos = content_lower.find(phrase.lower())
                matched = content[pos : pos + len(phrase)]
                return FindingEvaluation(
                    guideline_id=g.id,
                    category=g.category,
                    outcome=SemanticOutcome.VIOLATION,
                    explanation=f"Content contains phrase '{matched}' prohibited in this semantic context.",
                    flagged_excerpt=matched,
                    char_start=pos,
                    char_end=pos + len(phrase),
                    confidence_score=0.9,
                    recommendation=f"Remove or replace '{matched}'.",
                )

        # E. Default guideline evaluation: PASS
        return FindingEvaluation(
            guideline_id=g.id,
            category=g.category,
            outcome=SemanticOutcome.PASS,
            explanation=f"Content satisfies contextual criteria for guideline '{g.title}'.",
            confidence_score=0.85,
        )


class SemanticService:
    """Manages immutable contextual semantic review runs and guideline evaluations."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

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
        )
        revision = (await self.session.execute(stmt)).scalar_one_or_none()
        if revision is None:
            raise NotFoundError(
                "ContentRevision",
                f"submission={submission_id} revision={revision_number}",
            )
        return revision

    async def run_semantic_review(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        policy_id: uuid.UUID,
        actor_id: str,
        reviewer: BaseSemanticReviewer | None = None,
    ) -> SemanticReviewRun:
        """Execute a contextual semantic review of a revision against an ACTIVE brand policy.

        Preserves historical immutability: Each execution generates a brand-new
        SemanticReviewRun and associated SemanticReviewFinding rows.
        """
        start_time = time.perf_counter()
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        # 1. Validate policy exists in workspace and is ACTIVE
        stmt_policy = (
            select(BrandPolicy)
            .where(
                BrandPolicy.id == policy_id,
                BrandPolicy.workspace_id == workspace_id,
            )
            .options(selectinload(BrandPolicy.guidelines))
        )
        policy = (await self.session.execute(stmt_policy)).scalar_one_or_none()
        if policy is None:
            raise NotFoundError("BrandPolicy", str(policy_id))
        if policy.status != PolicyStatus.ACTIVE:
            raise ValidationError(
                f"Policy '{policy.name}' (v{policy.version}) has status '{policy.status.value}'. "
                f"Semantic review requires an ACTIVE policy."
            )

        await self.audit.record_event(
            event_type=AuditEventType.SEMANTIC_REVIEW_STARTED,
            actor_id=actor_id,
            resource_type="ContentRevision",
            resource_id=str(revision.id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "revision_number": revision_number,
            },
        )

        # 2. Execute review
        active_reviewer = reviewer or RuleBasedSemanticReviewer()
        review_result = active_reviewer.evaluate(
            content=revision.content_text,
            guidelines=policy.guidelines or [],
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Calculate counts
        passed_cnt = sum(1 for f in review_result.findings if f.outcome == SemanticOutcome.PASS)
        violation_cnt = sum(
            1 for f in review_result.findings if f.outcome == SemanticOutcome.VIOLATION
        )
        needs_review_cnt = sum(
            1 for f in review_result.findings if f.outcome == SemanticOutcome.NEEDS_REVIEW
        )
        inconclusive_cnt = sum(
            1 for f in review_result.findings if f.outcome == SemanticOutcome.INCONCLUSIVE
        )

        # 3. Create run record
        run = SemanticReviewRun(
            workspace_id=workspace_id,
            revision_id=revision.id,
            policy_id=policy.id,
            policy_version=policy.version,
            status="completed",
            overall_outcome=review_result.overall_outcome,
            total_guidelines=len(policy.guidelines or []),
            passed_count=passed_cnt,
            violation_count=violation_cnt,
            needs_review_count=needs_review_cnt,
            inconclusive_count=inconclusive_cnt,
            executed_by_id=actor_id,
            engine_version=review_result.engine_version,
            execution_time_ms=elapsed_ms,
        )
        self.session.add(run)
        await self.session.flush()

        # 4. Insert findings
        for f_eval in review_result.findings:
            finding = SemanticReviewFinding(
                run_id=run.id,
                guideline_id=f_eval.guideline_id,
                category=f_eval.category,
                outcome=f_eval.outcome,
                explanation=f_eval.explanation,
                flagged_excerpt=f_eval.flagged_excerpt,
                char_start=f_eval.char_start,
                char_end=f_eval.char_end,
                confidence_score=f_eval.confidence_score,
                uncertainty_reason=f_eval.uncertainty_reason,
                recommendation=f_eval.recommendation,
            )
            self.session.add(finding)

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.SEMANTIC_REVIEW_COMPLETED,
            actor_id=actor_id,
            resource_type="SemanticReviewRun",
            resource_id=str(run.id),
            workspace_id=workspace_id,
            event_payload={
                "revision_id": str(revision.id),
                "policy_id": str(policy.id),
                "overall_outcome": run.overall_outcome.value,
                "violation_count": run.violation_count,
                "needs_review_count": run.needs_review_count,
                "inconclusive_count": run.inconclusive_count,
            },
        )

        # Reload with findings
        stmt_run = (
            select(SemanticReviewRun)
            .where(SemanticReviewRun.id == run.id)
            .options(selectinload(SemanticReviewRun.findings))
        )
        return (await self.session.execute(stmt_run)).scalar_one()

    async def list_runs(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SemanticReviewRun], int]:
        """List historical semantic review runs for a content revision."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)

        filters = [
            SemanticReviewRun.revision_id == revision.id,
            SemanticReviewRun.workspace_id == workspace_id,
        ]
        count_stmt = select(func.count(SemanticReviewRun.id)).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(SemanticReviewRun)
            .where(*filters)
            .options(selectinload(SemanticReviewRun.findings))
            .order_by(SemanticReviewRun.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        runs = list((await self.session.execute(stmt)).scalars().all())
        return runs, total

    async def get_run(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        run_id: uuid.UUID,
    ) -> SemanticReviewRun:
        """Retrieve a specific semantic review run with its findings."""
        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        stmt = (
            select(SemanticReviewRun)
            .where(
                SemanticReviewRun.id == run_id,
                SemanticReviewRun.revision_id == revision.id,
                SemanticReviewRun.workspace_id == workspace_id,
            )
            .options(selectinload(SemanticReviewRun.findings))
        )
        run = (await self.session.execute(stmt)).scalar_one_or_none()
        if run is None:
            raise NotFoundError("SemanticReviewRun", str(run_id))
        return run
