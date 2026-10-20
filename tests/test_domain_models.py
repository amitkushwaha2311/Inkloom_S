"""Tests for foundational domain models, constraints, and relationships."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    AuditEventType,
    EvidenceReferenceType,
    FindingCategory,
    PolicyStatus,
    ReviewDecisionType,
    SeverityLevel,
    SubmissionStatus,
    WorkspaceRole,
)
from app.domain.models import (
    AuditEvent,
    BrandPolicy,
    BrandWorkspace,
    ContentRevision,
    ContentSubmission,
    EvidenceReference,
    PolicyGuideline,
    ReviewDecision,
    VerificationFinding,
    WorkspaceMember,
)


@pytest.mark.asyncio
async def test_workspace_and_member_creation(db_session: AsyncSession):
    """Verify workspace creation and membership association."""
    workspace = BrandWorkspace(
        name="Acme Global",
        slug="acme-global",
        description="Global brand governance workspace",
        settings={"enforce_double_approval": True},
    )
    db_session.add(workspace)
    await db_session.flush()

    assert workspace.id is not None
    assert workspace.is_active is True
    assert workspace.created_at is not None

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="usr_01",
        email="compliance@acme.com",
        role=WorkspaceRole.ADMIN,
    )
    db_session.add(member)
    await db_session.flush()

    # Query back
    result = await db_session.execute(
        select(BrandWorkspace).where(BrandWorkspace.slug == "acme-global")
    )
    fetched_ws = result.scalar_one()
    assert fetched_ws.name == "Acme Global"
    assert len(fetched_ws.members) == 1
    assert fetched_ws.members[0].role == WorkspaceRole.ADMIN


@pytest.mark.asyncio
async def test_duplicate_workspace_member_fails_unique_constraint(db_session: AsyncSession):
    """Verify unique constraint prevents duplicate user membership in the same workspace."""
    workspace = BrandWorkspace(name="Nike", slug="nike")
    db_session.add(workspace)
    await db_session.flush()

    member1 = WorkspaceMember(workspace_id=workspace.id, user_id="usr_dup", email="u1@nike.com")
    member2 = WorkspaceMember(workspace_id=workspace.id, user_id="usr_dup", email="u2@nike.com")

    db_session.add(member1)
    await db_session.flush()

    db_session.add(member2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_policy_and_guideline_versioning(db_session: AsyncSession):
    """Verify brand policies support versioning and categorized guidelines."""
    workspace = BrandWorkspace(name="Apex Tech", slug="apex-tech")
    db_session.add(workspace)
    await db_session.flush()

    policy_v1 = BrandPolicy(
        workspace_id=workspace.id,
        name="Marketing Tone Guidelines",
        version=1,
        status=PolicyStatus.ACTIVE,
        created_by_id="usr_policy_author",
    )
    db_session.add(policy_v1)
    await db_session.flush()

    guideline = PolicyGuideline(
        policy_id=policy_v1.id,
        category=FindingCategory.RESTRICTED_CLAIMS,
        title="Prohibit Absolute Guarantees",
        rule_text="Do not claim '100% guarantee' without legal qualification.",
        examples_approved=["Engineered for high reliability under standard conditions"],
        examples_prohibited=["100% guaranteed never to fail"],
        severity_default=SeverityLevel.HIGH,
        is_mandatory=True,
    )
    db_session.add(guideline)
    await db_session.flush()

    # Create policy version 2
    policy_v2 = BrandPolicy(
        workspace_id=workspace.id,
        name="Marketing Tone Guidelines",
        version=2,
        status=PolicyStatus.DRAFT,
        created_by_id="usr_policy_author",
    )
    db_session.add(policy_v2)
    await db_session.flush()

    # Refresh policy_v1 to load guidelines collection asynchronously
    await db_session.refresh(policy_v1, ["guidelines"])

    assert policy_v1.version == 1
    assert policy_v2.version == 2
    assert len(policy_v1.guidelines) == 1
    assert policy_v1.guidelines[0].category == FindingCategory.RESTRICTED_CLAIMS


@pytest.mark.asyncio
async def test_content_submission_and_revision_history(db_session: AsyncSession):
    """Verify content drafts maintain sequential immutable revision records."""
    workspace = BrandWorkspace(name="Tesla", slug="tesla")
    db_session.add(workspace)
    await db_session.flush()

    submission = ContentSubmission(
        workspace_id=workspace.id,
        title="Q3 Press Release Announcement",
        campaign_tag="q3-launch",
        status=SubmissionStatus.SUBMITTED,
        author_id="usr_author_1",
    )
    db_session.add(submission)
    await db_session.flush()

    rev1 = ContentRevision(
        submission_id=submission.id,
        revision_number=1,
        content_text="# Announcement\n\nOur breakthrough platform launches today.",
        content_format="markdown",
    )
    db_session.add(rev1)
    await db_session.flush()

    rev2 = ContentRevision(
        submission_id=submission.id,
        revision_number=2,
        content_text="# Announcement\n\nOur verified platform launches today with partner support.",
        content_format="markdown",
    )
    db_session.add(rev2)
    await db_session.flush()

    await db_session.refresh(submission, ["revisions"])

    assert len(submission.revisions) == 2
    assert submission.revisions[0].revision_number == 1
    assert submission.revisions[1].revision_number == 2


@pytest.mark.asyncio
async def test_verification_findings_and_evidence(db_session: AsyncSession):
    """Verify findings attach to revisions and link back to evidence references."""
    workspace = BrandWorkspace(name="Stripe", slug="stripe")
    db_session.add(workspace)
    await db_session.flush()

    submission = ContentSubmission(
        workspace_id=workspace.id,
        title="Homepage Hero Copy",
        author_id="usr_writer",
    )
    db_session.add(submission)
    await db_session.flush()

    revision = ContentRevision(
        submission_id=submission.id,
        revision_number=1,
        content_text="We offer the cheapest rates anywhere.",
    )
    db_session.add(revision)
    await db_session.flush()

    finding = VerificationFinding(
        revision_id=revision.id,
        category=FindingCategory.BRAND_VOICE,
        severity=SeverityLevel.HIGH,
        message="Superlative 'cheapest' violates premium brand positioning guidelines.",
        flagged_excerpt="the cheapest rates anywhere",
        char_start=13,
        char_end=40,
        recommendation="Replace with 'transparent, competitive pricing'.",
    )
    db_session.add(finding)
    await db_session.flush()

    evidence = EvidenceReference(
        finding_id=finding.id,
        reference_type=EvidenceReferenceType.APPROVED_LEXICON,
        source_identifier="BRAND-GUIDE-SEC-3",
        source_url="https://internal.brand.guide/terminology",
        excerpt_quote="Avoid bottom-tier price framing like 'cheapest'. Prefer 'value-focused' or 'competitive'.",
        confidence_score=0.96,
    )
    db_session.add(evidence)
    await db_session.flush()

    await db_session.refresh(finding, ["evidence_references"])

    assert finding.id is not None
    assert len(finding.evidence_references) == 1
    assert finding.evidence_references[0].confidence_score == 0.96


@pytest.mark.asyncio
async def test_review_decision_lifecycle(db_session: AsyncSession):
    """Verify human reviewer approval decisions record rationale and status."""
    workspace = BrandWorkspace(name="Figma", slug="figma")
    db_session.add(workspace)
    await db_session.flush()

    sub = ContentSubmission(workspace_id=workspace.id, title="Blog Post", author_id="u1")
    db_session.add(sub)
    await db_session.flush()

    rev = ContentRevision(submission_id=sub.id, revision_number=1, content_text="Draft post")
    db_session.add(rev)
    await db_session.flush()

    decision = ReviewDecision(
        submission_id=sub.id,
        revision_id=rev.id,
        reviewer_id="reviewer_lead",
        decision=ReviewDecisionType.REQUEST_CHANGES,
        rationale_summary="Tone in paragraph 2 needs adjustment before sign-off.",
        feedback_notes="Please address the flagged superlatives and resubmit.",
    )
    db_session.add(decision)
    await db_session.flush()

    assert decision.id is not None
    assert decision.decision == ReviewDecisionType.REQUEST_CHANGES
    assert decision.decided_at is not None


@pytest.mark.asyncio
async def test_audit_event_immutability(db_session: AsyncSession):
    """Verify audit events are append-only and record complete event context."""
    audit = AuditEvent(
        event_type=AuditEventType.POLICY_PUBLISHED,
        actor_id="admin_user_99",
        resource_type="BrandPolicy",
        resource_id="pol_12345",
        event_payload={"policy_name": "Tone Guide", "version": 2},
        ip_address_hash="a1b2c3d4e5f6...",
        user_agent_snippet="Mozilla/5.0 (Macintosh)",
    )
    db_session.add(audit)
    await db_session.flush()

    assert audit.id is not None
    assert audit.occurred_at is not None
    assert not hasattr(audit, "updated_at")  # AuditEvent has no updated_at (immutable)

    # Verify that updating an AuditEvent raises ValueError
    audit.actor_id = "malicious_actor"
    with pytest.raises(ValueError, match="AuditEvent records are append-only: updates are prohibited"):
        await db_session.flush()
    await db_session.rollback()

    # Verify that deleting an AuditEvent raises ValueError
    fresh_audit = AuditEvent(
        event_type=AuditEventType.POLICY_PUBLISHED,
        actor_id="admin_user_99",
        resource_type="BrandPolicy",
        resource_id="pol_12345",
        event_payload={"policy_name": "Tone Guide", "version": 2},
    )
    db_session.add(fresh_audit)
    await db_session.flush()

    await db_session.delete(fresh_audit)
    with pytest.raises(ValueError, match="AuditEvent records are append-only: deletions are prohibited"):
        await db_session.flush()
    await db_session.rollback()
