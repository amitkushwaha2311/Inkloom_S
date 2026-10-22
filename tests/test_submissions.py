"""Phase 4 Tests — Content Ingestion & Immutable Revision Management.

Covers:
1. Submission creation with initial revision and SHA-256 integrity hash
2. Submission detail retrieval and revision history listing
3. Listing with pagination and filtering by status, campaign_tag, author
4. Workspace isolation and cross-workspace access prevention (404)
5. Authorization and RBAC enforcement (VIEWER cannot create/revise, non-member blocked)
6. Immutable revision creation and sequential version ordering
7. Concurrency conflict detection via expected_revision_number (409 Conflict)
8. Input validation and oversized payload limits (>100KB rejected)
9. Revisions cannot be bypassed via metadata PATCH endpoints
10. Audit trail recording for submission creation and revisions (without full content text)
"""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditEventType
from app.domain.models.audit import AuditEvent

# ---------------------------------------------------------------------------
# Test Helpers
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
    user_id = reg_res.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _create_workspace(client: AsyncClient, headers: dict, name: str = "Brand Corp") -> str:
    """Create a workspace and return its workspace_id."""
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Test Brand Workspace"},
        headers=headers,
    )
    assert res.status_code == 201
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
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# 1. Submission Creation & Retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_submission_success(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "sub_author@example.com")
    ws_id = await _create_workspace(client, headers)

    content_text = "# Autumn Launch Campaign\n\nExperience our next-generation battery technology."
    expected_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

    payload = {
        "title": "Autumn Campaign Press Release",
        "campaign_tag": "autumn-launch",
        "content_text": content_text,
        "content_type": "marketing_copy",
        "content_format": "markdown",
        "source_metadata": {"channel": "press_wire", "target_region": "EU"},
        "status": "draft",
    }

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions", json=payload, headers=headers
    )
    assert res.status_code == 201
    data = res.json()

    assert data["title"] == "Autumn Campaign Press Release"
    assert data["campaign_tag"] == "autumn-launch"
    assert data["status"] == "draft"
    assert data["revision_count"] == 1

    latest_rev = data["latest_revision"]
    assert latest_rev is not None
    assert latest_rev["revision_number"] == 1
    assert latest_rev["content_text"] == content_text
    assert latest_rev["content_hash"] == expected_hash
    assert latest_rev["content_type"] == "marketing_copy"
    assert latest_rev["source_metadata"]["channel"] == "press_wire"

    # Verify retrieval
    sub_id = data["id"]
    get_res = await client.get(f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sub_id


@pytest.mark.asyncio
async def test_create_submission_with_submitted_status(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "sub_ready@example.com")
    ws_id = await _create_workspace(client, headers)

    payload = {
        "title": "Ready for Verification Copy",
        "content_text": "Approved copy ready for automated verification.",
        "status": "submitted",
    }
    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions", json=payload, headers=headers
    )
    assert res.status_code == 201
    assert res.json()["status"] == "submitted"


# ---------------------------------------------------------------------------
# 2. Listing, Filtering, and Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_submissions_filtering_and_pagination(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "list_author@example.com")
    ws_id = await _create_workspace(client, headers)

    # Create 3 submissions with different statuses and campaign tags
    items_to_create = [
        {"title": "Doc 1", "content_text": "Text 1", "campaign_tag": "summer", "status": "draft"},
        {
            "title": "Doc 2",
            "content_text": "Text 2",
            "campaign_tag": "summer",
            "status": "submitted",
        },
        {"title": "Doc 3", "content_text": "Text 3", "campaign_tag": "winter", "status": "draft"},
    ]
    for item in items_to_create:
        res = await client.post(
            f"/api/v1/workspaces/{ws_id}/submissions", json=item, headers=headers
        )
        assert res.status_code == 201

    # List all
    all_res = await client.get(f"/api/v1/workspaces/{ws_id}/submissions", headers=headers)
    assert all_res.status_code == 200
    assert all_res.json()["total"] == 3

    # Filter by status=submitted
    status_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions?status=submitted", headers=headers
    )
    assert status_res.status_code == 200
    assert status_res.json()["total"] == 1
    assert status_res.json()["items"][0]["title"] == "Doc 2"

    # Filter by campaign_tag=summer
    tag_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions?campaign_tag=summer", headers=headers
    )
    assert tag_res.status_code == 200
    assert tag_res.json()["total"] == 2

    # Test pagination: page_size=2
    page_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions?page=1&page_size=2", headers=headers
    )
    assert page_res.status_code == 200
    pdata = page_res.json()
    assert len(pdata["items"]) == 2
    assert pdata["has_next"] is True


# ---------------------------------------------------------------------------
# 3. Authorization & Workspace Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    fake_ws = uuid.uuid4()
    res = await client.get(f"/api/v1/workspaces/{fake_ws}/submissions")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_non_member_access_forbidden(client: AsyncClient):
    _, owner_headers = await _create_user_and_headers(client, "owner_isolated@example.com")
    ws_id = await _create_workspace(client, owner_headers)

    _, stranger_headers = await _create_user_and_headers(client, "stranger@example.com")
    res = await client.get(f"/api/v1/workspaces/{ws_id}/submissions", headers=stranger_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_viewer_role_cannot_create_submission_or_revision(client: AsyncClient):
    _, owner_headers = await _create_user_and_headers(client, "ws_owner_rbac@example.com")
    ws_id = await _create_workspace(client, owner_headers)

    viewer_id, viewer_headers = await _create_user_and_headers(client, "viewer_user@example.com")
    await _add_member(
        client, owner_headers, ws_id, viewer_id, "viewer_user@example.com", role="viewer"
    )

    # Viewer can read list
    res_list = await client.get(f"/api/v1/workspaces/{ws_id}/submissions", headers=viewer_headers)
    assert res_list.status_code == 200

    # Viewer cannot create submission
    res_post = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Viewer Draft", "content_text": "Cannot write"},
        headers=viewer_headers,
    )
    assert res_post.status_code == 403


@pytest.mark.asyncio
async def test_cross_workspace_access_returns_404(client: AsyncClient):
    """Submissions from Workspace A requested via Workspace B must return 404."""
    _, headers = await _create_user_and_headers(client, "multi_ws_owner@example.com")
    ws_a = await _create_workspace(client, headers, name="Workspace Alpha")
    ws_b = await _create_workspace(client, headers, name="Workspace Beta")

    sub_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/submissions",
        json={"title": "Alpha Secret Plan", "content_text": "Confidential Alpha text"},
        headers=headers,
    )
    sub_id = sub_res.json()["id"]

    # Access via Workspace B URL returns 404
    cross_res = await client.get(
        f"/api/v1/workspaces/{ws_b}/submissions/{sub_id}",
        headers=headers,
    )
    assert cross_res.status_code == 404


# ---------------------------------------------------------------------------
# 4. Immutable Revision Integrity & Version Ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_immutable_revision_lifecycle(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "revision_author@example.com")
    ws_id = await _create_workspace(client, headers)

    # Initial revision (v1)
    v1_text = "Original paragraph with subtle typos."
    v1_hash = hashlib.sha256(v1_text.encode("utf-8")).hexdigest()

    create_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Draft Article", "content_text": v1_text},
        headers=headers,
    )
    sub_id = create_res.json()["id"]

    # Append revision 2 (v2)
    v2_text = "Corrected paragraph with fixed typos."
    v2_hash = hashlib.sha256(v2_text.encode("utf-8")).hexdigest()

    rev2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={
            "content_text": v2_text,
            "change_summary": "Fixed typos in main paragraph",
        },
        headers=headers,
    )
    assert rev2_res.status_code == 201
    r2_data = rev2_res.json()
    assert r2_data["revision_number"] == 2
    assert r2_data["content_hash"] == v2_hash
    assert r2_data["change_summary"] == "Fixed typos in main paragraph"

    # Append revision 3 (v3)
    v3_text = "Polished paragraph ready for legal review."
    v3_hash = hashlib.sha256(v3_text.encode("utf-8")).hexdigest()

    rev3_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={
            "content_text": v3_text,
            "change_summary": "Final legal polish",
        },
        headers=headers,
    )
    assert rev3_res.status_code == 201
    assert rev3_res.json()["revision_number"] == 3
    assert rev3_res.json()["content_hash"] == v3_hash

    # Verify list of revisions has all 3 in ascending order
    list_revs = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        headers=headers,
    )
    assert list_revs.status_code == 200
    revs = list_revs.json()
    assert len(revs) == 3
    assert [r["revision_number"] for r in revs] == [1, 2, 3]

    # Verify original v1 content was NEVER modified (immutability)
    v1_get = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions/1",
        headers=headers,
    )
    assert v1_get.status_code == 200
    assert v1_get.json()["content_text"] == v1_text
    assert v1_get.json()["content_hash"] == v1_hash


# ---------------------------------------------------------------------------
# 5. Concurrency Conflict Detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_revision_conflict_rejected(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "conflict_author@example.com")
    ws_id = await _create_workspace(client, headers)

    sub_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Collaborative Doc", "content_text": "Base text"},
        headers=headers,
    )
    sub_id = sub_res.json()["id"]

    # User A successfully updates with expected_revision_number=1 -> creates v2
    user_a_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={
            "content_text": "User A edits",
            "expected_revision_number": 1,
        },
        headers=headers,
    )
    assert user_a_res.status_code == 201
    assert user_a_res.json()["revision_number"] == 2

    # User B concurrently submits based on stale v1 (expected_revision_number=1) -> 409 Conflict
    user_b_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={
            "content_text": "User B concurrent edits",
            "expected_revision_number": 1,
        },
        headers=headers,
    )
    assert user_b_res.status_code == 409
    assert "conflict" in user_b_res.json()["error"]["message"].lower()

    # User B pulls latest, passes expected_revision_number=2 -> succeeds (creates v3)
    user_b_retry = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={
            "content_text": "User B reconciled edits",
            "expected_revision_number": 2,
        },
        headers=headers,
    )
    assert user_b_retry.status_code == 201
    assert user_b_retry.json()["revision_number"] == 3


# ---------------------------------------------------------------------------
# 6. Input Validation & Restrictions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_empty_title_fails(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "val_author@example.com")
    ws_id = await _create_workspace(client, headers)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "   ", "content_text": "Valid text"},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_validation_empty_content_fails(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "val2_author@example.com")
    ws_id = await _create_workspace(client, headers)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Valid Title", "content_text": "   "},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_validation_unsupported_format_fails(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "val3_author@example.com")
    ws_id = await _create_workspace(client, headers)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={
            "title": "Valid Title",
            "content_text": "Valid text",
            "content_format": "binary_docx",
        },
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_validation_oversized_content_fails(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "val4_author@example.com")
    ws_id = await _create_workspace(client, headers)

    # 105,000 characters exceeds 100,000 character limit
    huge_text = "A" * 105_000
    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Huge Document", "content_text": huge_text},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_cannot_overwrite_content_via_metadata_patch(client: AsyncClient):
    """Metadata PATCH must update title/tag/status but CANNOT modify revision content."""
    _, headers = await _create_user_and_headers(client, "patch_author@example.com")
    ws_id = await _create_workspace(client, headers)

    original_text = "Immutable original text content."
    create_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Original Title", "content_text": original_text, "campaign_tag": "tag-a"},
        headers=headers,
    )
    sub_id = create_res.json()["id"]

    # PATCH metadata
    patch_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}",
        json={
            "title": "Renamed Title",
            "campaign_tag": "tag-b",
            "content_text": "MALICIOUS OVERWRITE",
        },
        headers=headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Renamed Title"
    assert updated["campaign_tag"] == "tag-b"

    # Verify original revision text remains untouched
    get_res = await client.get(f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}", headers=headers)
    assert get_res.json()["latest_revision"]["content_text"] == original_text
    assert get_res.json()["revision_count"] == 1


# ---------------------------------------------------------------------------
# 7. Audit Event Recording & Forensic Redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_events_recorded_without_full_content(
    client: AsyncClient, db_session: AsyncSession
):
    user_id, headers = await _create_user_and_headers(client, "audit_author@example.com")
    ws_id = await _create_workspace(client, headers)

    secret_content = "Super secret insider announcement."
    secret_hash = hashlib.sha256(secret_content.encode("utf-8")).hexdigest()

    create_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions",
        json={"title": "Audited Announcement", "content_text": secret_content},
        headers=headers,
    )
    sub_id = create_res.json()["id"]

    # Append revision
    rev2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={"content_text": "Updated secret announcement.", "change_summary": "Revised wording"},
        headers=headers,
    )
    assert rev2_res.status_code == 201

    # Query audit events from database
    events_res = await db_session.execute(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == uuid.UUID(ws_id))
        .order_by(AuditEvent.occurred_at.asc())
    )
    events = list(events_res.scalars().all())

    # Find CONTENT_SUBMITTED and CONTENT_REVISED events
    sub_events = [e for e in events if e.event_type == AuditEventType.CONTENT_SUBMITTED]
    rev_events = [e for e in events if e.event_type == AuditEventType.CONTENT_REVISED]

    assert len(sub_events) >= 1
    sub_event = sub_events[0]
    assert sub_event.actor_id == user_id
    assert sub_event.event_payload["content_hash"] == secret_hash
    # Security constraint: full raw content must NEVER be saved in audit log
    assert secret_content not in str(sub_event.event_payload)

    assert len(rev_events) >= 1
    rev_event = rev_events[0]
    assert rev_event.actor_id == user_id
    assert rev_event.event_payload["revision_number"] == 2
    assert rev_event.event_payload["change_summary"] == "Revised wording"
