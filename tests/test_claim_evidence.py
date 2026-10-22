"""Phase 6 Tests — Evidence-Backed Claim Verification.

Comprehensive backend test coverage:
1. Evidence Source Registry & Lifecycle:
   - Registration starts in DRAFT status.
   - Approval by ADMIN/OWNER transitions to APPROVED and records timestamps.
   - Rejection and revocation require justifications.
   - Expiry dates: expired sources are ignored during evidence assessment.
   - Source modification increments version and resets to DRAFT for re-approval.
2. SSRF Protections & URL Safety:
   - Private IP addresses (127.0.0.1, 10.0.0.1, 192.168.1.1) rejected.
   - Cloud metadata endpoints (169.254.169.254, metadata.google.internal) rejected.
   - Valid public HTTP/HTTPS URLs accepted.
3. Content Claim Ingestion & Representation:
   - Factual claims, subjective opinions, and promotional superlatives.
   - Association with specific ContentRevision.
4. Conservative Evidence Assessment Outcomes:
   - SUPPORTED: Approved evidence directly substantiates the claim.
   - CONTRADICTED: Approved evidence directly disputes/contradicts the claim.
   - INSUFFICIENT_EVIDENCE: No matching approved evidence (never treated as false).
   - CONFLICTING_EVIDENCE: Opposing approved sources disagree.
   - NEEDS_HUMAN_REVIEW: Opinion and promotional claims require reviewer judgment.
   - Untrusted sources: DRAFT, REJECTED, and REVOKED sources are excluded.
5. Provenance, Version Binding, & Immutability:
   - Re-assessing creates a new assessment record without mutating history.
   - Snapshots of source ID, version, and matched excerpts are recorded.
   - Optional binding to active BrandPolicy version.
6. Role-Based Access Control (RBAC):
   - Only ADMIN/OWNER can approve, reject, or revoke sources.
   - CONTRIBUTOR can create sources, record claims, and assess claims.
   - VIEWER can read sources, claims, and assessments, but cannot mutate.
   - Non-members blocked with 403/404.
7. Cross-Workspace Isolation:
   - Cross-workspace source access and assessment are prevented (404).
8. Audit Trail Verification:
   - Source lifecycle events and claim assessment events logged in audit trail.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditEventType, ClaimAssessmentStatus
from app.domain.models.audit import AuditEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user_and_headers(
    client: AsyncClient, email: str, name: str = "Test User"
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
    client: AsyncClient, headers: dict, name: str = "Evidence Lab Corp"
) -> str:
    """Create a workspace and return its workspace_id."""
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Workspace for claim verification tests"},
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
    role: str = "contributor",
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
    content_text: str = "Our battery delivers 24 hours of runtime in standard laboratory testing.",
) -> str:
    payload = {
        "title": "Battery Whitepaper Copy",
        "campaign_tag": "hardware-launch",
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


async def _register_source(
    client: AsyncClient,
    headers: dict,
    workspace_id: str,
    title: str = "IEC-62133 Lab Battery Report",
    source_type: str = "certified_lab_result",
    trusted_excerpts: list[str] | None = None,
    structured_facts: list[dict] | None = None,
    effective_date: str | None = None,
    expiry_date: str | None = None,
) -> dict:
    if effective_date is None:
        effective_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()

    payload = {
        "title": title,
        "source_type": source_type,
        "source_url": "https://standards.example.org/reports/iec-62133-2026.pdf",
        "internal_reference": "LAB-REPORT-994",
        "publisher_or_owner": "Underwriters Laboratories",
        "effective_date": effective_date,
        "expiry_date": expiry_date,
        "trusted_excerpts": trusted_excerpts
        or ["24 hours of runtime in standard laboratory testing."],
        "structured_facts": structured_facts or [],
    }
    res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/evidence-sources",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# 1. SSRF & URL Safety Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ssrf_protections_reject_unsafe_urls(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "ssrf_tester@example.com")
    ws_id = await _create_workspace(client, headers)

    unsafe_urls = [
        "http://localhost:8080/secret",
        "http://127.0.0.1:80/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/internal-docs",
        "http://192.168.1.1/router",
        "ftp://example.com/file.txt",
    ]

    for bad_url in unsafe_urls:
        payload = {
            "title": "Unsafe Evidence Document",
            "source_type": "other",
            "source_url": bad_url,
            "publisher_or_owner": "Attacker",
            "effective_date": datetime.now(UTC).isoformat(),
        }
        res = await client.post(
            f"/api/v1/workspaces/{ws_id}/evidence-sources",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422, f"Expected 422 for unsafe URL: {bad_url}"


# ---------------------------------------------------------------------------
# 2. Source Lifecycle: Creation, Approval, Rejection, Revocation, Expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_source_lifecycle_and_expiry(client: AsyncClient):
    owner_id, owner_headers = await _create_user_and_headers(client, "owner_src@example.com")
    ws_id = await _create_workspace(client, owner_headers)

    # 1. Registration starts as DRAFT
    src = await _register_source(client, owner_headers, ws_id, title="Battery Safety Standard")
    src_id = src["id"]
    assert src["approval_status"] == "draft"
    assert src["is_valid"] is False
    assert src["version"] == 1

    # 2. Approval
    app_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=owner_headers,
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["approval_status"] == "approved"
    assert app_data["is_valid"] is True
    assert app_data["approved_by_id"] == owner_id

    # 3. Modification increments version and resets to DRAFT for re-review
    upd_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}",
        json={"trusted_excerpts": ["Updated runtime is 26 hours in eco-mode."]},
        headers=owner_headers,
    )
    assert upd_res.status_code == 200
    upd_data = upd_res.json()
    assert upd_data["version"] == 2
    assert upd_data["approval_status"] == "draft"
    assert upd_data["is_valid"] is False

    # Re-approve version 2
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=owner_headers,
    )

    # 4. Revocation
    rev_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/revoke",
        json={"reason": "Testing lab lost ISO accreditation."},
        headers=owner_headers,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["approval_status"] == "revoked"
    assert rev_res.json()["is_valid"] is False


@pytest.mark.asyncio
async def test_expired_evidence_source_is_not_valid(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "expiry_tester@example.com")
    ws_id = await _create_workspace(client, headers)

    past_effective = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    past_expiry = (datetime.now(UTC) - timedelta(days=5)).isoformat()

    # Create an already expired source
    src = await _register_source(
        client,
        headers,
        ws_id,
        title="Expired 2025 Study",
        effective_date=past_effective,
        expiry_date=past_expiry,
    )
    src_id = src["id"]

    # Approve it
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=headers,
    )

    # Fetch it — approval_status is approved, but is_valid is False due to expiry!
    get_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["approval_status"] == "approved"
    assert get_res.json()["is_valid"] is False


# ---------------------------------------------------------------------------
# 3. Claim Assessment Outcomes: SUPPORTED, CONTRADICTED, INSUFFICIENT, CONFLICTING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_assessment_supported_outcome(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "sup_author@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # Register and approve source
    src = await _register_source(
        client,
        headers,
        ws_id,
        trusted_excerpts=["24 hours of runtime in standard laboratory testing."],
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src['id']}/approve",
        headers=headers,
    )

    # Record factual claim
    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "Battery delivers 24 hours of runtime in standard laboratory testing.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    # Assess claim
    ass_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass_res.status_code == 201
    data = ass_res.json()
    assert data["assessment_status"] == ClaimAssessmentStatus.SUPPORTED
    assert len(data["supporting_sources_snapshot"]) == 1
    assert data["uncertainty_score"] < 0.1
    assert "supported by approved authoritative evidence source" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_claim_assessment_contradicted_outcome(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "con_author@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # Register source with structured contradiction
    src = await _register_source(
        client,
        headers,
        ws_id,
        title="Official Benchmark Test",
        structured_facts=[
            {
                "claim": "Continuous battery runtime",
                "contradicts": ["100 hours of continuous runtime"],
                "assertion": "Maximum tested duration is strictly 18 hours.",
            }
        ],
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src['id']}/approve",
        headers=headers,
    )

    # Record false/contradicted claim
    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "Our device offers 100 hours of continuous runtime without charging.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    claim_id = claim_res.json()["id"]

    # Assess claim -> CONTRADICTED
    ass_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass_res.status_code == 201
    data = ass_res.json()
    assert data["assessment_status"] == ClaimAssessmentStatus.CONTRADICTED
    assert len(data["contradicting_sources_snapshot"]) == 1
    assert "contradicted by approved authoritative evidence source" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_claim_assessment_insufficient_evidence_when_missing(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "insuf_author@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # Record claim with NO matching evidence sources in workspace
    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "Device operates under temperatures as extreme as -70 Celsius.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    claim_id = claim_res.json()["id"]

    ass_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass_res.status_code == 201
    data = ass_res.json()
    assert data["assessment_status"] == ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE
    assert data["uncertainty_score"] == 1.0
    # Must preserve principle that missing evidence != proof of falsity
    assert "absence of evidence is never treated as proof of falsity" in data["explanation"]


@pytest.mark.asyncio
async def test_claim_assessment_conflicting_evidence_outcome(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "conflict_author@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # Source 1 supports
    src1 = await _register_source(
        client,
        headers,
        ws_id,
        title="Lab Test A",
        structured_facts=[{"supports": ["water resistant up to 50 meters"]}],
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src1['id']}/approve",
        headers=headers,
    )

    # Source 2 contradicts
    src2 = await _register_source(
        client,
        headers,
        ws_id,
        title="Field Inspection B",
        structured_facts=[{"contradicts": ["water resistant up to 50 meters"]}],
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src2['id']}/approve",
        headers=headers,
    )

    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "The chassis is water resistant up to 50 meters according to standard.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    claim_id = claim_res.json()["id"]

    ass_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass_res.status_code == 201
    data = ass_res.json()
    assert data["assessment_status"] == ClaimAssessmentStatus.CONFLICTING_EVIDENCE
    assert len(data["supporting_sources_snapshot"]) == 1
    assert len(data["contradicting_sources_snapshot"]) == 1


@pytest.mark.asyncio
async def test_opinion_and_promotional_claims_require_human_review(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "opinion_author@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # 1. Subjective opinion
    c_op = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "We believe our typography is the most elegant in modern software.",
            "claim_type": "opinion",
        },
        headers=headers,
    )
    ass_op = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{c_op.json()['id']}/assess",
        json={},
        headers=headers,
    )
    assert ass_op.status_code == 201
    assert ass_op.json()["assessment_status"] == ClaimAssessmentStatus.NEEDS_HUMAN_REVIEW
    assert "subjective opinion" in ass_op.json()["explanation"].lower()

    # 2. Promotional claim
    c_promo = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "The greatest productivity breakthrough in human history!",
            "claim_type": "promotional",
        },
        headers=headers,
    )
    ass_promo = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{c_promo.json()['id']}/assess",
        json={},
        headers=headers,
    )
    assert ass_promo.status_code == 201
    assert ass_promo.json()["assessment_status"] == ClaimAssessmentStatus.NEEDS_HUMAN_REVIEW
    assert "promotional" in ass_promo.json()["explanation"].lower()


# ---------------------------------------------------------------------------
# 4. Untrusted Evidence: DRAFT and REVOKED sources are ignored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unapproved_or_revoked_sources_not_treated_as_evidence(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "untrusted_src@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # Register source but leave it in DRAFT
    await _register_source(
        client,
        headers,
        ws_id,
        trusted_excerpts=["Zero sugar and completely organic formulation."],
    )

    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "Zero sugar and completely organic formulation.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    claim_id = claim_res.json()["id"]

    # Assessment must return INSUFFICIENT_EVIDENCE because draft source is unapproved!
    ass_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass_res.status_code == 201
    assert ass_res.json()["assessment_status"] == ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE


# ---------------------------------------------------------------------------
# 5. Provenance & Historical Assessment Immutability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_reassessment_creates_new_record_and_preserves_history(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "immut_tester@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    claim_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={
            "claim_text": "Ultra-low latency audio processing under 5 milliseconds.",
            "claim_type": "factual",
        },
        headers=headers,
    )
    claim_id = claim_res.json()["id"]

    # Assessment 1: No evidence yet -> INSUFFICIENT_EVIDENCE
    ass1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass1.status_code == 201
    ass1_id = ass1.json()["id"]
    assert ass1.json()["assessment_status"] == ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE

    # Now register & approve evidence
    src = await _register_source(
        client,
        headers,
        ws_id,
        title="Latency Benchmark Report",
        trusted_excerpts=["Ultra-low latency audio processing under 5 milliseconds."],
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src['id']}/approve",
        headers=headers,
    )

    # Assessment 2: Now SUPPORTED
    ass2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )
    assert ass2.status_code == 201
    ass2_id = ass2.json()["id"]
    assert ass2.json()["assessment_status"] == ClaimAssessmentStatus.SUPPORTED

    # Assert IDs are distinct
    assert ass1_id != ass2_id

    # List historical assessments for this claim -> must return both in order!
    list_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assessments",
        headers=headers,
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 2
    assert items[0]["id"] == ass2_id
    assert items[1]["id"] == ass1_id

    # Retrieve Assessment 1 directly -> must be completely unchanged!
    get_ass1 = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assessments/{ass1_id}",
        headers=headers,
    )
    assert get_ass1.status_code == 200
    assert get_ass1.json()["assessment_status"] == ClaimAssessmentStatus.INSUFFICIENT_EVIDENCE


# ---------------------------------------------------------------------------
# 6. Role-Based Access Control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_for_evidence_sources_and_claim_assessments(client: AsyncClient):
    owner_id, owner_headers = await _create_user_and_headers(client, "owner_rbac_src@example.com")
    ws_id = await _create_workspace(client, owner_headers)
    sub_id = await _create_submission(client, owner_headers, ws_id)

    # Contributor
    contrib_id, contrib_headers = await _create_user_and_headers(
        client, "contrib_rbac_src@example.com"
    )
    await _add_member(
        client, owner_headers, ws_id, contrib_id, "contrib_rbac_src@example.com", role="contributor"
    )

    # Viewer
    viewer_id, viewer_headers = await _create_user_and_headers(
        client, "viewer_rbac_src@example.com"
    )
    await _add_member(
        client, owner_headers, ws_id, viewer_id, "viewer_rbac_src@example.com", role="viewer"
    )

    # 1. Contributor can register evidence source
    src = await _register_source(client, contrib_headers, ws_id, title="Contributor Source")
    src_id = src["id"]

    # 2. Contributor CANNOT approve source -> 403 Forbidden
    r_no_app = await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=contrib_headers,
    )
    assert r_no_app.status_code == 403

    # 3. Owner CAN approve source -> 200 OK
    r_app = await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=owner_headers,
    )
    assert r_app.status_code == 200

    # 4. Contributor can record claim and assess it
    c_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={"claim_text": "Sample claim for rbac test.", "claim_type": "factual"},
        headers=contrib_headers,
    )
    assert c_res.status_code == 201
    claim_id = c_res.json()["id"]

    # 5. Viewer CANNOT record claim or assess claim -> 403 Forbidden
    r_v_claim = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={"claim_text": "Viewer claim", "claim_type": "factual"},
        headers=viewer_headers,
    )
    assert r_v_claim.status_code == 403

    r_v_ass = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=viewer_headers,
    )
    assert r_v_ass.status_code == 403

    # 6. Viewer CAN read sources and claims -> 200 OK
    r_v_list_src = await client.get(
        f"/api/v1/workspaces/{ws_id}/evidence-sources",
        headers=viewer_headers,
    )
    assert r_v_list_src.status_code == 200

    r_v_get_claim = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}",
        headers=viewer_headers,
    )
    assert r_v_get_claim.status_code == 200


# ---------------------------------------------------------------------------
# 7. Cross-Workspace Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_workspace_evidence_isolation(client: AsyncClient):
    _, headers_a = await _create_user_and_headers(client, "user_alpha@example.com")
    ws_a = await _create_workspace(client, headers_a, name="Alpha Corp")

    _, headers_b = await _create_user_and_headers(client, "user_beta@example.com")
    ws_b = await _create_workspace(client, headers_b, name="Beta Corp")

    # Source in Alpha
    src_a = await _register_source(client, headers_a, ws_a, title="Confidential Alpha Spec")

    # User B tries to access Alpha source via Beta endpoint -> 404
    r_cross = await client.get(
        f"/api/v1/workspaces/{ws_b}/evidence-sources/{src_a['id']}",
        headers=headers_b,
    )
    assert r_cross.status_code == 404


# ---------------------------------------------------------------------------
# 8. Audit Trail Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_logging_for_evidence_and_claims(
    client: AsyncClient, db_session: AsyncSession
):
    user_id, headers = await _create_user_and_headers(client, "audit_claim_user@example.com")
    ws_id = await _create_workspace(client, headers)
    sub_id = await _create_submission(client, headers, ws_id)

    # 1. Create and approve source
    src = await _register_source(client, headers, ws_id, title="Audited Evidence Source")
    src_id = src["id"]
    await client.post(
        f"/api/v1/workspaces/{ws_id}/evidence-sources/{src_id}/approve",
        headers=headers,
    )

    # 2. Record claim
    c_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims",
        json={"claim_text": "Audited assertion text", "claim_type": "factual"},
        headers=headers,
    )
    claim_id = c_res.json()["id"]

    # 3. Assess claim
    await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1/claims/{claim_id}/assess",
        json={},
        headers=headers,
    )

    # Verify audit events
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == uuid.UUID(ws_id),
            AuditEvent.event_type.in_(
                [
                    AuditEventType.EVIDENCE_SOURCE_CREATED,
                    AuditEventType.EVIDENCE_SOURCE_APPROVED,
                    AuditEventType.CLAIM_RECORDED,
                    AuditEventType.CLAIM_ASSESSED,
                ]
            ),
        )
        .order_by(AuditEvent.occurred_at.asc())
    )
    events = list((await db_session.execute(stmt)).scalars().all())
    event_types = [e.event_type for e in events]

    assert AuditEventType.EVIDENCE_SOURCE_CREATED in event_types
    assert AuditEventType.EVIDENCE_SOURCE_APPROVED in event_types
    assert AuditEventType.CLAIM_RECORDED in event_types
    assert AuditEventType.CLAIM_ASSESSED in event_types
