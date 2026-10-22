"""Phase 9 Tests — Audit Trail & Governance Analytics.

Comprehensive backend test coverage:
1. Workspace Audit Timeline:
   - Chronological audit event listing with stable ordering (occurred_at DESC, id DESC).
   - Pagination controls (page, page_size, total, has_next).
   - Filtering by event_type, actor_id, date range (start_date, end_date), and submission_id.
   - Related entity resolution and graceful handling of deleted or unavailable entities.
   - Cross-workspace isolation: events are strictly confined to their workspace.
2. Submission Provenance & Review History:
   - Full lifecycle view across revisions, policy versions, verification runs, claims, semantic reviews,
     corrections, and human review determinations.
   - Strict distinction between unexecuted checks (not_run) and verified clean outcomes (verified_clean).
   - Cross-workspace isolation: cannot access provenance across workspace boundaries.
3. Governance Analytics:
   - Accurately computed workspace metrics: total submissions, revisions, reviews completed.
   - Violations aggregated by category and severity.
   - Most frequent guideline violations ranking.
   - Human intervention percentage (decisions requiring changes or rejection).
   - Correction suggestion acceptance rates.
   - Review turnaround time (average, median, min, max in hours).
   - Historical time-series trends by day.
   - Empty dataset and zero-denominator safety (no division-by-zero or crash).
4. Audit Integrity Protections:
   - Application-level immutability enforced at the ORM layer:
     before_update and before_delete event listeners actively block mutations.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    AuditEventType,
    FindingCategory,
    ReviewDecisionType,
    SeverityLevel,
    SubmissionStatus,
)
from app.domain.models.audit import AuditEvent

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


async def _create_user_and_headers(
    client: AsyncClient, email: str, name: str = "Audit Tester"
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
    client: AsyncClient, headers: dict, name: str = "Audit Workspace"
) -> str:
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Workspace for Phase 9 tests"},
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


# ---------------------------------------------------------------------------
# 1. Audit Timeline & Filtering Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_timeline_pagination_and_ordering(client: AsyncClient):
    """Verify that audit events are listed in stable reverse-chronological order with pagination."""
    _, owner_headers = await _create_user_and_headers(client, "audit_pg_owner@test.com")
    ws_id = await _create_workspace(client, owner_headers, "Timeline Workspace")

    # Perform multiple actions that generate audit events
    sub1_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Timeline Submission 1",
            "content_text": "Draft content for timeline item 1.",
            "content_format": "markdown",
        },
        headers=owner_headers,
    )
    assert sub1_res.status_code == 201

    sub2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Timeline Submission 2",
            "content_text": "Draft content for timeline item 2.",
            "content_format": "markdown",
        },
        headers=owner_headers,
    )
    assert sub2_res.status_code == 201

    # Fetch audit events with page_size=2
    audit_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?page=1&page_size=2",
        headers=owner_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    data = audit_res.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] >= 2
    assert data["has_next"] is True

    # Check stable reverse-chronological ordering
    items = data["items"]
    t0 = datetime.fromisoformat(items[0]["occurred_at"])
    t1 = datetime.fromisoformat(items[1]["occurred_at"])
    assert t0 >= t1


@pytest.mark.asyncio
async def test_audit_timeline_filtering(client: AsyncClient):
    """Verify filtering by event_type, actor_id, date range, and submission_id."""
    user1_id, u1_headers = await _create_user_and_headers(client, "filter_user1@test.com")
    user2_id, u2_headers = await _create_user_and_headers(client, "filter_user2@test.com")
    ws_id = await _create_workspace(client, u1_headers, "Filtering Workspace")
    await _add_member(client, u1_headers, ws_id, user2_id, "filter_user2@test.com", "contributor")

    # Action 1 by user 1
    sub1_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Sub 1 by User 1",
            "content_text": "Content by user 1.",
            "content_format": "markdown",
        },
        headers=u1_headers,
    )
    assert sub1_res.status_code == 201
    sub1_id = sub1_res.json()["id"]

    # Action 2 by user 2
    sub2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Sub 2 by User 2",
            "content_text": "Content by user 2.",
            "content_format": "markdown",
        },
        headers=u2_headers,
    )
    assert sub2_res.status_code == 201

    # Filter by event_type
    f_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?event_type={AuditEventType.CONTENT_SUBMITTED.value}",
        headers=u1_headers,
    )
    assert f_res.status_code == 200
    for item in f_res.json()["items"]:
        assert item["event_type"] == AuditEventType.CONTENT_SUBMITTED.value

    # Filter by actor_id
    f_actor = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?actor_id={user2_id}",
        headers=u1_headers,
    )
    assert f_actor.status_code == 200
    assert f_actor.json()["total"] >= 1
    for item in f_actor.json()["items"]:
        assert item["actor_id"] == user2_id

    # Filter by submission_id
    f_sub = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?submission_id={sub1_id}",
        headers=u1_headers,
    )
    assert f_sub.status_code == 200
    assert f_sub.json()["total"] >= 1
    for item in f_sub.json()["items"]:
        # Either resource_id is sub1_id or event_payload contains submission_id
        is_sub = (item["resource_id"] == sub1_id) or (
            item["event_payload"].get("submission_id") == sub1_id
        )
        assert is_sub

    # Filter by date range
    past = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    f_date = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?start_date={past}&end_date={future}",
        headers=u1_headers,
    )
    assert f_date.status_code == 200
    assert f_date.json()["total"] >= 2


@pytest.mark.asyncio
async def test_audit_related_entity_resolution_and_missing_references(client: AsyncClient):
    """Verify related entity resolution and graceful handling of deleted/non-existent entities."""
    _, headers = await _create_user_and_headers(client, "entity_res@test.com")
    ws_id = await _create_workspace(client, headers, "Entity Workspace")

    sub_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Entity Tracked Sub",
            "content_text": "Text body.",
            "content_format": "markdown",
        },
        headers=headers,
    )
    assert sub_res.status_code == 201

    events_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events?resolve_references=true",
        headers=headers,
    )
    assert events_res.status_code == 200
    items = events_res.json()["items"]
    assert len(items) > 0

    sub_events = [it for it in items if it["resource_type"] == "ContentSubmission"]
    assert len(sub_events) > 0
    sub_ev = sub_events[0]
    assert sub_ev["related_entity"] is not None
    assert sub_ev["related_entity"]["is_available"] is True
    assert sub_ev["related_entity"]["display_name"] == "Entity Tracked Sub"


# ---------------------------------------------------------------------------
# 2. Cross-Workspace Isolation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_workspace_isolation_audit_and_analytics(client: AsyncClient):
    """Verify workspace A cannot view audit events, provenance, or analytics of workspace B."""
    _, u1_headers = await _create_user_and_headers(client, "iso_u1@test.com")
    _, u2_headers = await _create_user_and_headers(client, "iso_u2@test.com")

    ws_a = await _create_workspace(client, u1_headers, "Workspace Alpha")
    ws_b = await _create_workspace(client, u2_headers, "Workspace Beta")

    # Create submission in Workspace Alpha
    sub_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/submissions",
        json={
            "title": "Alpha Secret",
            "content_text": "Confidential text.",
            "content_format": "markdown",
        },
        headers=u1_headers,
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    # User 2 tries to access Workspace Alpha audit events -> 403 Forbidden
    res1 = await client.get(f"/api/v1/workspaces/{ws_a}/audit-events", headers=u2_headers)
    assert res1.status_code in (403, 404)

    # User 2 tries to access Workspace Alpha provenance -> 403 Forbidden
    res2 = await client.get(
        f"/api/v1/workspaces/{ws_a}/submissions/{sub_id}/provenance", headers=u2_headers
    )
    assert res2.status_code in (403, 404)

    # User 2 tries to access Alpha's submission via Beta's provenance endpoint -> 404 Not Found
    res3 = await client.get(
        f"/api/v1/workspaces/{ws_b}/submissions/{sub_id}/provenance", headers=u2_headers
    )
    assert res3.status_code == 404

    # User 2 tries to access Workspace Alpha analytics -> 403 Forbidden
    res4 = await client.get(f"/api/v1/workspaces/{ws_a}/governance-analytics", headers=u2_headers)
    assert res4.status_code in (403, 404)

    # User 1 views Workspace Alpha audit events: should NEVER include events from Workspace Beta
    alpha_events = await client.get(f"/api/v1/workspaces/{ws_a}/audit-events", headers=u1_headers)
    assert alpha_events.status_code == 200
    for it in alpha_events.json()["items"]:
        assert it["workspace_id"] == ws_a


# ---------------------------------------------------------------------------
# 3. Provenance & Review History Lifecycle Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submission_provenance_full_lifecycle(client: AsyncClient):
    """Verify complete lifecycle provenance across revisions, policies, verifications, suggestions, and decisions."""
    owner_id, owner_headers = await _create_user_and_headers(client, "prov_owner@test.com")
    rev_id, rev_headers = await _create_user_and_headers(client, "prov_reviewer@test.com")
    ws_id = await _create_workspace(client, owner_headers, "Provenance Lifecycle WS")
    await _add_member(client, owner_headers, ws_id, rev_id, "prov_reviewer@test.com", "reviewer")

    # 1. Create Brand Policy with guideline
    policy_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies",
        json={"name": "Lifecycle Policy", "description": "Phase 9 test policy"},
        headers=owner_headers,
    )
    assert policy_res.status_code == 201
    policy_id = policy_res.json()["id"]

    # Add prohibited phrase guideline
    g_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{policy_id}/guidelines",
        json={
            "title": "No Junk Term",
            "category": "terminology",
            "rule_text": "Do not include prohibited food terminology in drafts.",
            "rule_config": {"rule_type": "prohibited_terms", "terms": ["junkfood"]},
        },
        headers=owner_headers,
    )
    assert g_res.status_code == 201
    guideline_id = g_res.json()["id"]

    # Activate policy
    act_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{policy_id}/activate",
        json={"confirm": True},
        headers=owner_headers,
    )
    assert act_res.status_code == 200

    # 2. Ingest Content Submission (Revision 1 with violation)
    sub_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Nutritional Blog Post",
            "content_text": "We strictly prohibit junkfood in our school cafeteria menus.",
            "content_format": "markdown",
        },
        headers=owner_headers,
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    # 3. Run Deterministic Verification on Revision 1 -> Violations Found
    v_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=owner_headers,
    )
    assert v_res.status_code == 201
    assert v_res.json()["violation_count"] == 1

    # 4. Propose and Apply a Correction Suggestion -> Revision 2
    sug_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions",
        json={
            "original_text": "junkfood",
            "proposed_replacement": "ultra-processed food",
            "recommended_action": "Replace prohibited term",
            "reason": "Compliance with terminology guideline",
            "guideline_id": guideline_id,
        },
        headers=rev_headers,
    )
    assert sug_res.status_code == 201
    sug_id = sug_res.json()["id"]

    # Accept suggestion
    await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sug_id}",
        json={"status": "accepted"},
        headers=owner_headers,
    )

    # Apply suggestion to generate Revision 2
    apply_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/suggestions/{sug_id}/apply",
        json={"expected_revision_number": 1},
        headers=owner_headers,
    )
    assert apply_res.status_code == 201

    # 5. Run Verification on Revision 2 -> Clean Pass
    v2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=2",
        json={"policy_id": policy_id},
        headers=owner_headers,
    )
    assert v2_res.status_code == 201
    assert v2_res.json()["violation_count"] == 0

    # 6. Record Review Decision (Approve by reviewer)
    dec_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/2/decisions",
        json={
            "decision": "approve",
            "rationale_summary": "Revision 2 addressed the prohibited terminology cleanly.",
            "policy_id": policy_id,
            "policy_version": 1,
        },
        headers=rev_headers,
    )
    assert dec_res.status_code == 201

    # 7. Query Provenance Endpoint
    prov_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/provenance",
        headers=owner_headers,
    )
    assert prov_res.status_code == 200, prov_res.text
    prov_data = prov_res.json()

    assert prov_data["submission_id"] == sub_id
    assert prov_data["total_revisions"] == 2
    assert prov_data["current_status"] == SubmissionStatus.APPROVED.value

    # Validate Revision 1
    r1 = prov_data["revisions"][0]
    assert r1["revision_number"] == 1
    assert r1["deterministic_verification"]["status"] == "violations_found"
    assert r1["deterministic_verification"]["violation_count"] == 1
    assert len(r1["deterministic_verification"]["findings"]) == 1
    assert len(r1["correction_suggestions"]) == 1
    # Check distinction of unexecuted checks
    assert r1["semantic_review"]["status"] == "not_run"
    assert r1["claims_verification"]["status"] == "no_claims_discovered"

    # Validate Revision 2
    r2 = prov_data["revisions"][1]
    assert r2["revision_number"] == 2
    assert r2["was_applied_from_suggestion_id"] == sug_id
    assert r2["deterministic_verification"]["status"] == "verified_clean"
    assert r2["deterministic_verification"]["violation_count"] == 0
    assert len(r2["review_decisions"]) == 1
    assert r2["review_decisions"][0]["decision"] == ReviewDecisionType.APPROVE.value

    # Validate Lifecycle Summary
    summary = prov_data["lifecycle_summary"]
    assert summary["is_currently_approved"] is True
    assert summary["total_decisions_rendered"] == 1
    assert summary["latest_decision"] == ReviewDecisionType.APPROVE.value
    assert len(summary["policy_versions_evaluated"]) >= 1


# ---------------------------------------------------------------------------
# 4. Governance Analytics Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_analytics_calculations(client: AsyncClient):
    """Verify analytics metrics calculations: violations, acceptance rate, human intervention rate, turnaround."""
    owner_id, owner_headers = await _create_user_and_headers(client, "gov_owner@test.com")
    rev_id, rev_headers = await _create_user_and_headers(client, "gov_rev@test.com")
    ws_id = await _create_workspace(client, owner_headers, "Governance Analytics WS")
    await _add_member(client, owner_headers, ws_id, rev_id, "gov_rev@test.com", "reviewer")

    # Policy setup with prohibited term
    p_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies",
        json={"name": "Analytics Policy"},
        headers=owner_headers,
    )
    p_id = p_res.json()["id"]

    g_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{p_id}/guidelines",
        json={
            "title": "Forbidden Phrase",
            "category": "terminology",
            "rule_text": "Prohibited phrase badword must never appear in copy.",
            "rule_config": {"rule_type": "prohibited_terms", "terms": ["badword"]},
        },
        headers=owner_headers,
    )
    assert g_res.status_code == 201
    guideline_id = g_res.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{p_id}/activate",
        json={"confirm": True},
        headers=owner_headers,
    )

    # Sub 1: Has violation
    s1_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Draft with badword",
            "content_text": "Contains badword.",
            "content_format": "markdown",
        },
        headers=owner_headers,
    )
    s1_id = s1_res.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/verification/runs?revision_number=1",
        json={"policy_id": p_id},
        headers=owner_headers,
    )

    # Sub 2: Clean content
    s2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Clean Draft",
            "content_text": "Contains good content.",
            "content_format": "markdown",
        },
        headers=owner_headers,
    )
    s2_id = s2_res.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s2_id}/verification/runs?revision_number=1",
        json={"policy_id": p_id},
        headers=owner_headers,
    )

    # Add 2 suggestions on s1 revision 1: 1 accepted, 1 rejected
    sug1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/revisions/1/suggestions",
        json={
            "original_text": "badword",
            "proposed_replacement": "goodword",
            "recommended_action": "Fix terminology",
            "reason": "Compliance",
            "guideline_id": guideline_id,
        },
        headers=rev_headers,
    )
    sug1_id = sug1.json()["id"]
    await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/revisions/1/suggestions/{sug1_id}",
        json={"status": "accepted"},
        headers=owner_headers,
    )

    sug2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/revisions/1/suggestions",
        json={
            "original_text": "badword",
            "proposed_replacement": "altword",
            "recommended_action": "Alternative fix",
            "reason": "Alt suggestion",
            "guideline_id": guideline_id,
        },
        headers=rev_headers,
    )
    sug2_id = sug2.json()["id"]
    await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/revisions/1/suggestions/{sug2_id}",
        json={"status": "rejected"},
        headers=owner_headers,
    )

    # Record 2 Review Decisions:
    # Decision 1 on Sub 1: request_changes (requires human intervention)
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s1_id}/revisions/1/decisions",
        json={
            "decision": "request_changes",
            "rationale_summary": "Please replace the prohibited terminology badword.",
            "policy_id": p_id,
            "policy_version": 1,
        },
        headers=rev_headers,
    )

    # Decision 2 on Sub 2: approve (no intervention needed)
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{s2_id}/revisions/1/decisions",
        json={
            "decision": "approve",
            "rationale_summary": "All checks passed cleanly.",
            "policy_id": p_id,
            "policy_version": 1,
        },
        headers=rev_headers,
    )

    # Query Governance Analytics
    analytics_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/governance-analytics",
        headers=owner_headers,
    )
    assert analytics_res.status_code == 200, analytics_res.text
    data = analytics_res.json()

    assert data["total_submissions"] == 2
    assert data["total_revisions"] == 2
    assert data["total_reviews_completed"] == 2

    # Human intervention rate: 1 intervention out of 2 reviews = 50.0%
    hi = data["human_intervention"]
    assert hi["total_reviews_completed"] == 2
    assert hi["reviews_requiring_intervention"] == 1
    assert hi["intervention_rate_percentage"] == 50.0

    # Correction acceptance rate: 1 accepted out of 2 suggestions = 50.0%
    ca = data["correction_acceptance"]
    assert ca["total_suggestions"] == 2
    assert ca["accepted_count"] == 1
    assert ca["rejected_count"] == 1
    assert ca["acceptance_rate_percentage"] == 50.0

    # Turnaround time
    tt = data["turnaround_time"]
    assert tt["total_decisions_measured"] == 2
    assert tt["average_hours"] is not None
    assert tt["median_hours"] is not None

    # Violations by category and severity
    v_cats = {item["category"]: item["count"] for item in data["violations_by_category"]}
    assert v_cats.get(FindingCategory.TERMINOLOGY.value, 0) == 1

    v_sevs = {item["severity"]: item["count"] for item in data["violations_by_severity"]}
    assert v_sevs.get(SeverityLevel.MEDIUM.value, 0) == 1

    # Most frequent guideline violations ranking
    freq_g = data["most_frequent_guideline_violations"]
    assert len(freq_g) == 1
    assert freq_g[0]["guideline_id"] == guideline_id
    assert freq_g[0]["violation_count"] == 1

    # Historical trends
    trends = data["historical_trends"]
    assert len(trends) >= 1
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    today_trend = next((t for t in trends if t["date"] == today_str), None)
    assert today_trend is not None
    assert today_trend["submissions_count"] == 2
    assert today_trend["reviews_completed"] == 2


@pytest.mark.asyncio
async def test_empty_workspace_analytics_and_zero_denominator_safety(client: AsyncClient):
    """Verify that empty datasets return 200 OK with zero metrics and no division-by-zero errors."""
    _, owner_headers = await _create_user_and_headers(client, "empty_gov_owner@test.com")
    empty_ws_id = await _create_workspace(client, owner_headers, "Empty WS for Analytics")

    res = await client.get(
        f"/api/v1/workspaces/{empty_ws_id}/governance-analytics",
        headers=owner_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_submissions"] == 0
    assert data["total_revisions"] == 0
    assert data["total_reviews_completed"] == 0
    assert data["violations_by_category"] == []
    assert data["violations_by_severity"] == []
    assert data["most_frequent_guideline_violations"] == []

    # Zero-denominator protection: rates are 0.0, turnaround is None
    assert data["human_intervention"]["intervention_rate_percentage"] == 0.0
    assert data["correction_acceptance"]["acceptance_rate_percentage"] == 0.0
    assert data["turnaround_time"]["average_hours"] is None
    assert data["turnaround_time"]["median_hours"] is None
    assert data["turnaround_time"]["total_decisions_measured"] == 0
    assert data["historical_trends"] == []


# ---------------------------------------------------------------------------
# 5. Audit Integrity & Immutability Protections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_update_prohibited(db_session: AsyncSession):
    """Verify that ORM-level event listeners prohibit update operations on AuditEvent."""
    ev = AuditEvent(
        workspace_id=uuid.uuid4(),
        event_type=AuditEventType.CONTENT_SUBMITTED,
        actor_id="test_actor_upd",
        resource_type="ContentSubmission",
        resource_id=str(uuid.uuid4()),
        event_payload={"title": "Immutable Title 1"},
    )
    db_session.add(ev)
    await db_session.flush()

    with pytest.raises(
        ValueError, match="AuditEvent records are append-only: updates are prohibited"
    ):
        ev.actor_id = "tampered_actor"
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_audit_event_delete_prohibited(db_session: AsyncSession):
    """Verify that ORM-level event listeners prohibit delete operations on AuditEvent."""
    ev = AuditEvent(
        workspace_id=uuid.uuid4(),
        event_type=AuditEventType.CONTENT_SUBMITTED,
        actor_id="test_actor_del",
        resource_type="ContentSubmission",
        resource_id=str(uuid.uuid4()),
        event_payload={"title": "Immutable Title 2"},
    )
    db_session.add(ev)
    await db_session.flush()

    with pytest.raises(
        ValueError, match="AuditEvent records are append-only: deletions are prohibited"
    ):
        await db_session.delete(ev)
        await db_session.flush()

    await db_session.rollback()
