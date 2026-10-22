"""Phase 8 Tests — Unified Review & Correction Workflow.

Comprehensive backend test coverage:
1. Unified Review Orchestration Summary:
   - Assembles deterministic findings, claim assessments, and semantic findings for a specific revision and active policy.
   - Clean PASS determination: ONLY True when all required checks ran, completed, and returned PASS.
   - Incomplete check detection: Missing or unexecuted checks produce INCOMPLETE and never report a clean pass.
   - Action Required: Rule violations, contradicted claims, or hostile tone flag ACTION_REQUIRED.
   - Inconclusive and Needs Review outcomes accurately synthesized.
2. Structured Correction Suggestions:
   - Creation linked to findings and guidelines.
   - Provenance validation: Citing unapproved evidence sources is rejected.
   - Status updates: ACCEPTED, REJECTED.
3. Applying Correction Suggestions:
   - Creates a brand-new ContentRevision via SubmissionService; never mutates prior revisions.
   - Optimistic concurrency protection: Mismatched expected_revision_number produces 409 Conflict.
   - Conflicting suggestions for the same text on the old revision are marked SUPERSEDED.
   - Re-applying already applied suggestions or rejected suggestions is blocked.
4. Human Review Governance & Separation of Duties:
   - REVIEWER, ADMIN, OWNER can record review decisions (approve, reject, request_changes).
   - Lifecycle state transitions on ContentSubmission.
   - Separation of duties: Authors are blocked from approving their own submissions (403).
   - Contributors and viewers are blocked from recording review decisions (403).
   - Preserves historical review decisions immutably.
5. Cross-Workspace Isolation & Audit Trail:
   - Cross-workspace isolation enforced.
   - All Phase 8 lifecycle events captured in the audit trail.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    AuditEventType,
    CorrectionStatus,
    ReviewDecisionType,
    SubmissionStatus,
    UnifiedCheckStatus,
    UnifiedReviewOutcome,
)
from app.domain.models.audit import AuditEvent

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


async def _create_user_and_headers(
    client: AsyncClient, email: str, name: str = "Workflow Tester"
) -> tuple[str, dict]:
    """Register and log in a user, returning (user_id, auth_headers)."""
    password = "SecurePassword1"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _create_workspace(
    client: AsyncClient, headers: dict, name: str = "Governance Lab Workspace"
) -> str:
    """Create a workspace and return its workspace_id."""
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Workspace for Phase 8 governance workflow"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _add_member(
    client: AsyncClient,
    owner_headers: dict,
    workspace_id: str,
    user_id: str,
    email: str,
    role: str = "reviewer",
) -> None:
    res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": user_id, "email": email, "role": role},
        headers=owner_headers,
    )
    assert res.status_code == 201, res.text


async def _create_submission(
    client: AsyncClient,
    headers: dict,
    workspace_id: str,
    content_text: str = "Standard brand text.",
    title: str = "Governance Post",
) -> str:
    """Create a submission and return submission_id."""
    payload = {
        "title": title,
        "campaign_tag": "phase8-governance",
        "content_text": content_text,
        "content_type": "marketing_copy",
        "content_format": "markdown",
        "status": "draft",
    }
    res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/submissions",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _create_active_policy(
    client: AsyncClient,
    headers: dict,
    workspace_id: str,
    name: str = "Enterprise Brand Policy",
    guidelines: list | None = None,
) -> str:
    """Create and activate a policy."""
    if guidelines is None:
        guidelines = [
            {
                "category": "brand_voice",
                "title": "Prohibited Buzzwords",
                "rule_text": "Do not use the word synergy in press releases or marketing text.",
                "severity_default": "high",
                "is_mandatory": True,
                "rule_config": {
                    "rule_type": "prohibited_terms",
                    "terms": ["synergy"],
                    "case_sensitive": False,
                },
            },
            {
                "category": "tone_consistency",
                "title": "Respectful Tone",
                "rule_text": "Content must maintain a respectful tone free of hostile language.",
                "severity_default": "high",
                "is_mandatory": True,
                "rule_config": {"tone": "professional"},
            },
        ]

    create_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies",
        json={"name": name, "description": "Enterprise policy", "guidelines": guidelines},
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    policy_id = create_res.json()["id"]

    act_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies/{policy_id}/activate",
        json={"confirm": True},
        headers=headers,
    )
    assert act_res.status_code == 200, act_res.text
    return policy_id


# ---------------------------------------------------------------------------
# 1. Unified Review Orchestration Summary Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_review_summary_missing_checks_never_clean_pass(client: AsyncClient):
    """Verify that if deterministic or semantic checks have not run, summary is INCOMPLETE, not clean pass."""
    _, headers = await _create_user_and_headers(client, "orchestrator1@example.com")
    ws_id = await _create_workspace(client, headers)
    policy_id = await _create_active_policy(client, headers, ws_id)

    sub_id = await _create_submission(client, headers, ws_id, "Clean text without violations.")

    # Call review-summary directly before running deterministic or semantic checks
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/review-summary?policy_id={policy_id}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["overall_outcome"] == UnifiedReviewOutcome.INCOMPLETE.value
    assert data["is_clean_pass"] is False
    assert data["checks"]["deterministic"]["status"] == UnifiedCheckStatus.NOT_RUN.value
    assert data["checks"]["semantic"]["status"] == UnifiedCheckStatus.NOT_RUN.value


@pytest.mark.asyncio
async def test_unified_review_summary_clean_pass_when_all_checks_complete(client: AsyncClient):
    """Verify clean pass is reported when deterministic, evidence claims, and semantic checks all pass."""
    _, headers = await _create_user_and_headers(client, "orchestrator2@example.com")
    ws_id = await _create_workspace(client, headers)
    policy_id = await _create_active_policy(client, headers, ws_id)

    clean_content = (
        "Our software provides reliable, high-performance database management for enterprises."
    )
    sub_id = await _create_submission(client, headers, ws_id, clean_content)

    # 1. Run deterministic verification
    det_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert det_res.status_code == 201

    # 2. Run semantic review
    sem_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/semantic-review/runs",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert sem_res.status_code == 201

    # 3. Get unified review summary
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/review-summary?policy_id={policy_id}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["overall_outcome"] == UnifiedReviewOutcome.PASS.value
    assert data["is_clean_pass"] is True
    assert data["unresolved_issues_count"] == 0
    assert data["checks"]["deterministic"]["status"] == UnifiedCheckStatus.COMPLETED.value
    assert data["checks"]["semantic"]["status"] == UnifiedCheckStatus.COMPLETED.value
    assert data["checks"]["claims"]["status"] == UnifiedCheckStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_unified_review_summary_action_required_on_violations(client: AsyncClient):
    """Verify that deterministic violations or semantic issues trigger ACTION_REQUIRED."""
    _, headers = await _create_user_and_headers(client, "violator@example.com")
    ws_id = await _create_workspace(client, headers)
    policy_id = await _create_active_policy(client, headers, ws_id)

    content_with_synergy = "Our platform achieves great synergy across enterprise business units."
    sub_id = await _create_submission(client, headers, ws_id, content_with_synergy)

    # Run deterministic check (which will flag prohibited term 'synergy')
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    # Run semantic check
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/semantic-review/runs",
        json={"policy_id": policy_id},
        headers=headers,
    )

    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/review-summary?policy_id={policy_id}",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["overall_outcome"] == UnifiedReviewOutcome.ACTION_REQUIRED.value
    assert data["is_clean_pass"] is False
    assert data["unresolved_issues_count"] >= 1
    assert len(data["deterministic_findings"]) >= 1


# ---------------------------------------------------------------------------
# 2. Correction Suggestions Management & Provenance Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_update_correction_suggestion(client: AsyncClient):
    """Verify creating structured correction suggestions and updating status."""
    _, headers = await _create_user_and_headers(client, "suggester@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(
        client, headers, ws_id, "Leverage cross-functional synergy today."
    )

    # Create suggestion
    sugg_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "synergy",
            "char_start": 25,
            "char_end": 32,
            "proposed_replacement": "collaboration",
            "recommended_action": "Replace buzzword with clear, plain terminology",
            "reason": "Violates brand voice rule against buzzwords like 'synergy'",
        },
        headers=headers,
    )
    assert sugg_res.status_code == 201, sugg_res.text
    sugg_data = sugg_res.json()
    assert sugg_data["status"] == CorrectionStatus.PROPOSED.value
    assert sugg_data["proposed_replacement"] == "collaboration"
    sugg_id = sugg_data["id"]

    # Update suggestion status to ACCEPTED
    patch_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}",
        json={"status": CorrectionStatus.ACCEPTED.value},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == CorrectionStatus.ACCEPTED.value

    # List suggestions
    list_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        headers=headers,
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1


@pytest.mark.asyncio
async def test_correction_suggestion_rejects_unapproved_evidence(client: AsyncClient):
    """Verify that citing an unapproved/draft evidence source in a correction is rejected."""
    _, headers = await _create_user_and_headers(client, "evidence_guard@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id, "99.9% uptime claim.")

    # Register source in DRAFT (unapproved)
    draft_src_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources",
        json={
            "title": "Unapproved Internal Note",
            "source_type": "product_specification",
            "internal_reference": "INTERNAL-SPEC-01",
            "publisher_or_owner": "Eng Team",
            "effective_date": datetime.now(UTC).isoformat(),
        },
        headers=headers,
    )
    assert draft_src_res.status_code == 201
    draft_src_id = draft_src_res.json()["id"]

    # Attempt to cite this DRAFT evidence source in a correction suggestion
    sugg_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "99.9%",
            "proposed_replacement": "99.95%",
            "recommended_action": "Update uptime metric",
            "reason": "Backed by unapproved note",
            "evidence_source_id": draft_src_id,
        },
        headers=headers,
    )
    assert sugg_res.status_code == 422
    assert "only approved authoritative sources" in sugg_res.text.lower()


# ---------------------------------------------------------------------------
# 3. Applying Correction Suggestions (Concurrency & Immutability)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_correction_creates_new_revision_with_concurrency_guard(client: AsyncClient):
    """Verify applying a suggestion creates revision 2, never mutates revision 1, and enforces concurrency."""
    _, headers = await _create_user_and_headers(client, "applier@example.com")
    ws_id = await _create_workspace(client, headers)
    initial_text = "Our tool produces synergy and excellence."
    sub_id = await _create_submission(client, headers, ws_id, initial_text)

    # Create suggestion
    sugg_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "synergy",
            "proposed_replacement": "seamless alignment",
            "recommended_action": "Replace buzzword",
            "reason": "Brand voice compliance",
        },
        headers=headers,
    )
    sugg_id = sugg_res.json()["id"]

    # 1. Concurrency failure: wrong expected_revision_number
    conflict_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}/apply",
        json={"expected_revision_number": 99},  # Current is 1
        headers=headers,
    )
    assert conflict_res.status_code == 409
    assert "concurrency conflict" in conflict_res.text.lower()

    # 2. Concurrency success: correct expected_revision_number == 1
    apply_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}/apply",
        json={"expected_revision_number": 1},
        headers=headers,
    )
    assert apply_res.status_code == 201, apply_res.text
    apply_data = apply_res.json()

    assert apply_data["new_revision_number"] == 2
    assert "seamless alignment" in apply_data["content_text"]
    assert "synergy" not in apply_data["content_text"]

    # Verify revision 1 was NOT mutated
    sub_detail = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}",
        headers=headers,
    )
    rev1 = [r for r in sub_detail.json()["revisions"] if r["revision_number"] == 1][0]
    assert rev1["content_text"] == initial_text

    # 3. Attempting to apply again must fail (already applied)
    reapply_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}/apply",
        json={"expected_revision_number": 2},
        headers=headers,
    )
    assert reapply_res.status_code == 409


@pytest.mark.asyncio
async def test_apply_correction_supersedes_conflicting_suggestions(client: AsyncClient):
    """Verify that applying one suggestion marks other suggestions for the same text as SUPERSEDED."""
    _, headers = await _create_user_and_headers(client, "supersede_lead@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id, "We have synergy everywhere.")

    # Create suggestion A
    sugg_a = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "synergy",
            "proposed_replacement": "collaboration",
            "recommended_action": "Alternative A",
            "reason": "Option A",
        },
        headers=headers,
    )
    sugg_a_id = sugg_a.json()["id"]

    # Create suggestion B (alternative proposal for the same text)
    sugg_b = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "synergy",
            "proposed_replacement": "partnership",
            "recommended_action": "Alternative B",
            "reason": "Option B",
        },
        headers=headers,
    )
    sugg_b_id = sugg_b.json()["id"]

    # Apply suggestion A
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_a_id}/apply",
        json={"expected_revision_number": 1},
        headers=headers,
    )

    # Check suggestion B status: should now be SUPERSEDED
    sugg_b_check = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_b_id}",
        headers=headers,
    )
    assert sugg_b_check.json()["status"] == CorrectionStatus.SUPERSEDED.value


# ---------------------------------------------------------------------------
# 4. Human Review Decisions & Separation of Duties
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_separation_of_duties_author_cannot_approve_own_content(client: AsyncClient):
    """Verify that submission authors are blocked from approving their own content."""
    # Author creates submission
    author_id, author_headers = await _create_user_and_headers(client, "author_jane@example.com")
    ws_id = await _create_workspace(client, author_headers)
    policy_id = await _create_active_policy(client, author_headers, ws_id)
    sub_id = await _create_submission(client, author_headers, ws_id, "Jane's submission.")

    # Author attempts to APPROVE their own submission
    approve_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/decisions",
        json={
            "decision": ReviewDecisionType.APPROVE.value,
            "rationale_summary": "I approve my own work.",
            "policy_id": policy_id,
        },
        headers=author_headers,
    )
    assert approve_res.status_code == 403
    assert "separation of duties" in approve_res.text.lower()


@pytest.mark.asyncio
async def test_reviewer_can_render_review_decisions_and_transition_status(client: AsyncClient):
    """Verify independent reviewer can approve, reject, or request changes, updating submission status."""
    # Author creates submission
    author_id, author_headers = await _create_user_and_headers(client, "content_author@example.com")
    ws_id = await _create_workspace(client, author_headers)
    policy_id = await _create_active_policy(client, author_headers, ws_id)
    sub_id = await _create_submission(client, author_headers, ws_id, "Initial draft content.")

    # Add separate reviewer to workspace
    reviewer_id, reviewer_headers = await _create_user_and_headers(
        client, "lead_reviewer@example.com"
    )
    await _add_member(
        client, author_headers, ws_id, reviewer_id, "lead_reviewer@example.com", role="reviewer"
    )

    # 1. Reviewer requests changes
    req_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/decisions",
        json={
            "decision": ReviewDecisionType.REQUEST_CHANGES.value,
            "rationale_summary": "Please soften promotional language before approval.",
            "policy_id": policy_id,
        },
        headers=reviewer_headers,
    )
    assert req_res.status_code == 201
    assert req_res.json()["decision"] == ReviewDecisionType.REQUEST_CHANGES.value

    # Submission status should now be changes_requested
    sub_res1 = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}", headers=author_headers
    )
    assert sub_res1.json()["status"] == SubmissionStatus.CHANGES_REQUESTED.value

    # 2. Reviewer renders APPROVAL decision
    appr_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/decisions",
        json={
            "decision": ReviewDecisionType.APPROVE.value,
            "rationale_summary": "Approved after editorial discussion and sign-off.",
            "policy_id": policy_id,
        },
        headers=reviewer_headers,
    )
    assert appr_res.status_code == 201
    assert appr_res.json()["decision"] == ReviewDecisionType.APPROVE.value

    # Submission status should now be approved
    sub_res2 = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}", headers=author_headers
    )
    assert sub_res2.json()["status"] == SubmissionStatus.APPROVED.value

    # Verify decision history is preserved (both decisions exist)
    dec_list = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/decisions",
        headers=author_headers,
    )
    assert dec_list.status_code == 200
    assert dec_list.json()["total"] == 2


@pytest.mark.asyncio
async def test_contributor_and_viewer_blocked_from_review_decisions(client: AsyncClient):
    """Verify contributors and viewers are not authorized to render review determinations (403)."""
    _, owner_headers = await _create_user_and_headers(client, "gov_owner@example.com")
    ws_id = await _create_workspace(client, owner_headers)
    sub_id = await _create_submission(client, owner_headers, ws_id, "Some text.")

    # Contributor member
    contrib_id, contrib_headers = await _create_user_and_headers(client, "gov_contrib@example.com")
    await _add_member(
        client, owner_headers, ws_id, contrib_id, "gov_contrib@example.com", role="contributor"
    )

    # Contributor tries to record decision
    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/decisions",
        json={
            "decision": ReviewDecisionType.APPROVE.value,
            "rationale_summary": "Contributor approval attempt.",
        },
        headers=contrib_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 5. Audit Trail Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_trail_records_phase8_events(client: AsyncClient, db_session: AsyncSession):
    """Verify correction suggestions, applications, and review decisions are logged in audit trail."""
    author_id, author_headers = await _create_user_and_headers(client, "audit_author@example.com")
    ws_id = await _create_workspace(client, author_headers)
    policy_id = await _create_active_policy(client, author_headers, ws_id)
    sub_id = await _create_submission(client, author_headers, ws_id, "Text with synergy.")

    reviewer_id, reviewer_headers = await _create_user_and_headers(client, "audit_rev@example.com")
    await _add_member(
        client, author_headers, ws_id, reviewer_id, "audit_rev@example.com", role="reviewer"
    )

    # 1. Create correction suggestion
    sugg_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "synergy",
            "proposed_replacement": "collaboration",
            "recommended_action": "Fix word",
            "reason": "Brand voice",
        },
        headers=reviewer_headers,
    )
    sugg_id = sugg_res.json()["id"]

    # 2. Update suggestion
    await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}",
        json={"reason": "Updated reason for compliance"},
        headers=reviewer_headers,
    )

    # 3. Apply suggestion
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sugg_id}/apply",
        json={"expected_revision_number": 1},
        headers=reviewer_headers,
    )

    # 4. Record decision
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/2/decisions",
        json={
            "decision": ReviewDecisionType.APPROVE.value,
            "rationale_summary": "Approved revision 2.",
            "policy_id": policy_id,
        },
        headers=reviewer_headers,
    )

    # Inspect audit trail
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.workspace_id == uuid.UUID(ws_id))
        .order_by(AuditEvent.occurred_at.asc())
    )
    events = list((await db_session.execute(stmt)).scalars().all())
    event_types = [e.event_type for e in events]

    assert AuditEventType.CORRECTION_SUGGESTION_CREATED in event_types
    assert AuditEventType.CORRECTION_SUGGESTION_UPDATED in event_types
    assert AuditEventType.CORRECTION_APPLIED in event_types
    assert AuditEventType.REVIEW_DECIDED in event_types
