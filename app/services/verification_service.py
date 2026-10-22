"""Inkloom Sentinel - Deterministic Brand Compliance Verification Service.

Runs a set of explicit, rule-based checks against a content revision and records
an immutable VerificationRun with individual VerificationFinding rows.

Supported deterministic rule types (stored in PolicyGuideline.rule_config):
    prohibited_terms  – flags any occurrence of a forbidden term/phrase.
    required_terms    – flags when a required term/phrase is absent.
    brand_spelling    – flags occurrences where the canonical brand name is
                        spelled or cased incorrectly.
    length_limit      – flags when word or character count is outside bounds.

No LLM, embedding model, or vector database is used in this service.

Authorization notice:
    Callers are responsible for verifying workspace membership and policy ownership
    before calling this service. The service trusts that passed IDs are pre-validated.

SQLAlchemy async note:
    All session operations use explicit select() with selectinload so that
    relationship loading is scheduled correctly inside the async greenlet.
"""

import re
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    EvidenceReferenceType,
    PolicyStatus,
)
from app.domain.models.policy import BrandPolicy, PolicyGuideline
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.domain.models.verification import (
    EvidenceReference,
    VerificationFinding,
    VerificationRun,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal rule evaluators
# ---------------------------------------------------------------------------


def _find_all_occurrences(
    text: str, term: str, *, case_sensitive: bool = False
) -> list[tuple[int, int]]:
    """Return (start, end) character spans for every match of ``term`` in ``text``."""
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(term), flags)
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def _word_count(text: str) -> int:
    return len(text.split())


def _char_count(text: str) -> int:
    return len(text)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class VerificationService:
    """Deterministic compliance engine that runs guideline rules against revisions."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _require_revision(
        self, submission_id: uuid.UUID, workspace_id: uuid.UUID, revision_number: int
    ) -> ContentRevision:
        """Load a ContentRevision and confirm its submission belongs to workspace."""
        result = await self.session.execute(
            select(ContentRevision)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(
                ContentRevision.submission_id == submission_id,
                ContentRevision.revision_number == revision_number,
                ContentSubmission.workspace_id == workspace_id,
            )
        )
        revision = result.scalar_one_or_none()
        if revision is None:
            raise NotFoundError(
                "ContentRevision",
                f"submission={submission_id} revision={revision_number}",
            )
        return revision

    async def _require_active_policy(
        self, workspace_id: uuid.UUID, policy_id: uuid.UUID
    ) -> BrandPolicy:
        """Load a policy that must be ACTIVE and belong to the workspace."""
        result = await self.session.execute(
            select(BrandPolicy)
            .where(
                BrandPolicy.id == policy_id,
                BrandPolicy.workspace_id == workspace_id,
            )
            .options(selectinload(BrandPolicy.guidelines))
        )
        policy = result.scalar_one_or_none()
        if policy is None:
            raise NotFoundError("BrandPolicy", str(policy_id))
        if policy.status != PolicyStatus.ACTIVE:
            raise ValidationError(
                f"Policy '{policy.name}' (v{policy.version}) has status "
                f"'{policy.status.value}'. Only ACTIVE policies may be used for verification."
            )
        return policy

    async def _require_run(
        self,
        run_id: uuid.UUID,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> VerificationRun:
        """Load a VerificationRun, confirming its revision belongs to the workspace."""
        result = await self.session.execute(
            select(VerificationRun)
            .join(ContentRevision, VerificationRun.revision_id == ContentRevision.id)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(
                VerificationRun.id == run_id,
                ContentRevision.submission_id == submission_id,
                ContentSubmission.workspace_id == workspace_id,
            )
            .options(
                selectinload(VerificationRun.findings).selectinload(
                    VerificationFinding.evidence_references
                )
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("VerificationRun", str(run_id))
        return run

    # ------------------------------------------------------------------
    # Rule evaluation
    # ------------------------------------------------------------------

    def _evaluate_guideline(
        self,
        guideline: PolicyGuideline,
        content: str,
    ) -> list[dict]:
        """Evaluate one guideline's rule_config against content.

        Returns a list of finding dicts (may be empty if the rule passes).
        Each finding dict has keys matching VerificationFinding column names.
        """
        cfg: dict = guideline.rule_config or {}
        rule_type: str | None = cfg.get("rule_type")

        if not rule_type:
            # No deterministic rule configured — skip silently
            return []

        findings: list[dict] = []

        if rule_type == "prohibited_terms":
            terms: list[str] = cfg.get("terms", [])
            case_sensitive: bool = cfg.get("case_sensitive", False)
            for term in terms:
                spans = _find_all_occurrences(content, term, case_sensitive=case_sensitive)
                for start, end in spans:
                    findings.append(
                        {
                            "category": guideline.category,
                            "severity": guideline.severity_default,
                            "message": (
                                f"Prohibited term detected: '{term}'. "
                                f"See guideline '{guideline.title}'."
                            ),
                            "flagged_excerpt": content[max(0, start - 20) : end + 20].strip(),
                            "char_start": start,
                            "char_end": end,
                            "recommendation": (
                                f"Remove or replace the term '{term}' to comply with "
                                f"'{guideline.title}'."
                            ),
                            "evidence_excerpt": term,
                        }
                    )

        elif rule_type == "required_terms":
            terms = cfg.get("terms", [])
            case_sensitive = cfg.get("case_sensitive", False)
            for term in terms:
                spans = _find_all_occurrences(content, term, case_sensitive=case_sensitive)
                if not spans:
                    findings.append(
                        {
                            "category": guideline.category,
                            "severity": guideline.severity_default,
                            "message": (
                                f"Required term missing: '{term}'. "
                                f"See guideline '{guideline.title}'."
                            ),
                            "flagged_excerpt": content[:120].strip() if content else "",
                            "char_start": None,
                            "char_end": None,
                            "recommendation": (
                                f"Include the required term '{term}' in the content to comply "
                                f"with '{guideline.title}'."
                            ),
                            "evidence_excerpt": term,
                        }
                    )

        elif rule_type == "brand_spelling":
            canonical: str = cfg.get("canonical_name", "")
            # Build regex: match any word boundary-delimited occurrence that doesn't
            # exactly match the canonical string (case-sensitively) but does match
            # case-insensitively.
            if canonical:
                # Find all case-insensitive matches; flag those that differ in spelling/case.
                pattern = re.compile(re.escape(canonical), re.IGNORECASE)
                for m in pattern.finditer(content):
                    matched_text = m.group(0)
                    if matched_text != canonical:
                        findings.append(
                            {
                                "category": guideline.category,
                                "severity": guideline.severity_default,
                                "message": (
                                    f"Brand name misspelled: found '{matched_text}', "
                                    f"expected '{canonical}'."
                                ),
                                "flagged_excerpt": content[
                                    max(0, m.start() - 20) : m.end() + 20
                                ].strip(),
                                "char_start": m.start(),
                                "char_end": m.end(),
                                "recommendation": (
                                    f"Replace '{matched_text}' with the canonical "
                                    f"brand name '{canonical}'."
                                ),
                                "evidence_excerpt": matched_text,
                            }
                        )

        elif rule_type == "length_limit":
            unit: str = cfg.get("unit", "words")  # "words" or "chars"
            min_count: int | None = cfg.get("min_count")
            max_count: int | None = cfg.get("max_count")

            count = _word_count(content) if unit == "words" else _char_count(content)

            violated = False
            direction = ""
            if min_count is not None and count < min_count:
                violated = True
                direction = f"below minimum ({count} {unit} < {min_count})"
            elif max_count is not None and count > max_count:
                violated = True
                direction = f"exceeds maximum ({count} {unit} > {max_count})"

            if violated:
                findings.append(
                    {
                        "category": guideline.category,
                        "severity": guideline.severity_default,
                        "message": (
                            f"Length limit violated: content is {direction}. "
                            f"See guideline '{guideline.title}'."
                        ),
                        "flagged_excerpt": content[:120].strip() if content else "",
                        "char_start": None,
                        "char_end": None,
                        "recommendation": (
                            f"Adjust content length to meet the {unit} limit "
                            f"defined in '{guideline.title}'."
                        ),
                        "evidence_excerpt": f"{count} {unit}",
                    }
                )

        return findings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_verification(
        self,
        workspace_id: uuid.UUID,
        submission_id: uuid.UUID,
        revision_number: int,
        policy_id: uuid.UUID,
        actor_id: str,
    ) -> VerificationRun:
        """Run deterministic verification on a revision against an ACTIVE policy.

        Persists a VerificationRun with one VerificationFinding per rule violation
        and attached EvidenceReference rows.  Idempotency is not enforced; callers
        may trigger multiple runs for the same (revision, policy) pair.

        Args:
            workspace_id: The workspace the submission and policy both belong to.
            submission_id: Parent ContentSubmission ID.
            revision_number: Which revision number to verify.
            policy_id: The ACTIVE BrandPolicy to verify against.
            actor_id: Resolved actor identity (from verified JWT).

        Returns:
            The persisted VerificationRun with eagerly loaded findings.

        Raises:
            NotFoundError: If the revision or policy cannot be found in the workspace.
            ValidationError: If the policy is not ACTIVE.
        """
        t_start = time.monotonic()

        revision = await self._require_revision(submission_id, workspace_id, revision_number)
        policy = await self._require_active_policy(workspace_id, policy_id)

        content: str = revision.content_text
        guidelines: list[PolicyGuideline] = [g for g in policy.guidelines if g.rule_config]

        await self.audit.record_event(
            event_type=AuditEventType.VERIFICATION_STARTED,
            actor_id=actor_id,
            resource_type="ContentRevision",
            resource_id=str(revision.id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "revision_number": revision_number,
                "rule_count": len(guidelines),
            },
        )

        # Evaluate all guidelines
        all_finding_dicts: list[tuple[PolicyGuideline, dict]] = []
        passed = 0
        for guideline in guidelines:
            violations = self._evaluate_guideline(guideline, content)
            if violations:
                for v in violations:
                    all_finding_dicts.append((guideline, v))
            else:
                passed += 1

        elapsed_ms = (time.monotonic() - t_start) * 1000

        # Persist VerificationRun
        run = VerificationRun(
            revision_id=revision.id,
            policy_id=policy.id,
            policy_version=policy.version,
            status="completed",
            total_rules=len(guidelines),
            passed_rules=passed,
            violation_count=len(all_finding_dicts),
            inconclusive_count=0,
            executed_by_id=actor_id,
            execution_time_ms=round(elapsed_ms, 3),
        )
        self.session.add(run)
        await self.session.flush()  # assigns run.id

        # Persist VerificationFinding + EvidenceReference rows
        for guideline, fdict in all_finding_dicts:
            finding = VerificationFinding(
                revision_id=revision.id,
                run_id=run.id,
                guideline_id=guideline.id,
                category=fdict["category"],
                severity=fdict["severity"],
                message=fdict["message"],
                flagged_excerpt=fdict["flagged_excerpt"],
                char_start=fdict.get("char_start"),
                char_end=fdict.get("char_end"),
                recommendation=fdict.get("recommendation"),
            )
            self.session.add(finding)
            await self.session.flush()  # assigns finding.id

            # Attach an evidence reference pointing to the triggering guideline
            evidence = EvidenceReference(
                finding_id=finding.id,
                reference_type=EvidenceReferenceType.POLICY_CLAUSE,
                source_identifier=f"guideline:{guideline.id}",
                excerpt_quote=fdict.get("evidence_excerpt", ""),
                confidence_score=1.0,
            )
            self.session.add(evidence)

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.VERIFICATION_COMPLETED,
            actor_id=actor_id,
            resource_type="VerificationRun",
            resource_id=str(run.id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "total_rules": run.total_rules,
                "passed_rules": run.passed_rules,
                "violation_count": run.violation_count,
                "execution_time_ms": run.execution_time_ms,
            },
        )

        logger.info(
            "verification_completed",
            run_id=str(run.id),
            revision_id=str(revision.id),
            policy_id=str(policy.id),
            violations=run.violation_count,
        )

        # Reload with findings eagerly loaded
        return await self._reload_run(run.id)

    async def _reload_run(self, run_id: uuid.UUID) -> VerificationRun:
        """Reload a VerificationRun with all relationships eagerly loaded."""
        result = await self.session.execute(
            select(VerificationRun)
            .where(VerificationRun.id == run_id)
            .options(
                selectinload(VerificationRun.findings).selectinload(
                    VerificationFinding.evidence_references
                )
            )
        )
        run = result.scalar_one()
        return run

    async def get_run(
        self,
        run_id: uuid.UUID,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> VerificationRun:
        """Retrieve a single VerificationRun with its findings and evidence references."""
        return await self._require_run(run_id, submission_id, workspace_id)

    async def list_runs(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
        revision_number: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[VerificationRun], int]:
        """List VerificationRuns for a submission with optional revision filter.

        Returns (items, total_count).
        """
        # Confirm workspace ownership via join
        base_filters = [
            ContentRevision.submission_id == submission_id,
            ContentSubmission.workspace_id == workspace_id,
        ]
        if revision_number is not None:
            base_filters.append(ContentRevision.revision_number == revision_number)

        count_q = (
            select(func.count(VerificationRun.id))
            .join(ContentRevision, VerificationRun.revision_id == ContentRevision.id)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(*base_filters)
        )
        total = (await self.session.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        items_q = (
            select(VerificationRun)
            .join(ContentRevision, VerificationRun.revision_id == ContentRevision.id)
            .join(ContentSubmission, ContentRevision.submission_id == ContentSubmission.id)
            .where(*base_filters)
            .options(
                selectinload(VerificationRun.findings).selectinload(
                    VerificationFinding.evidence_references
                )
            )
            .order_by(VerificationRun.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        items = list((await self.session.execute(items_q)).scalars().all())
        return items, total
