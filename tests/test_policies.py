"""Phase 2 Tests — Brand Policy Management: CRUD, Lifecycle, Versioning.

Tests cover:
- Policy creation, listing, detail retrieval
- DRAFT-only editing enforcement
- Version forking from ACTIVE
- History listing
- Lifecycle transitions: DRAFT→ACTIVE, ACTIVE→DEPRECATED, ACTIVE→ARCHIVED, invalid transitions
- Activation requires ≥1 guideline
- Auto-deprecation of previous ACTIVE version on activation
- Cross-workspace access prevention (404 returned, not 403 to avoid info leakage)
- Name conflict detection
- No partial records on rollback
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.domain.enums import WorkspaceRole
from app.domain.models.user import User
from app.domain.models.workspace import BrandWorkspace, WorkspaceMember

WORKSPACE_ID = None  # set per-test

_TEST_USER: User | None = None


@pytest_asyncio.fixture(autouse=True)
async def setup_test_auth(client: AsyncClient, db_session: AsyncSession):
    global _TEST_USER
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"tester-{user_id.hex[:8]}@example.com",
        hashed_password=hash_password("Pass1234"),
        full_name="Test Actor",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    _TEST_USER = user

    token = create_access_token(
        payload={"sub": str(user.id), "email": user.email, "type": "sentinel_access"},
        secret_key=settings.SECRET_KEY,
    )
    client.headers["Authorization"] = f"Bearer {token}"
    yield
    client.headers.pop("Authorization", None)
    _TEST_USER = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_GUIDELINE = {
    "category": "brand_voice",
    "title": "Use Active Voice",
    "rule_text": "All marketing copy must use active voice construction in sentences.",
    "severity_default": "medium",
    "is_mandatory": True,
    "examples_approved": ["We deliver results."],
    "examples_prohibited": ["Results are delivered by us."],
}


async def _make_workspace(db_session: AsyncSession, name: str = "TestCorp") -> BrandWorkspace:
    ws = BrandWorkspace(name=name, slug=f"testcorp-{uuid.uuid4().hex[:8]}")
    db_session.add(ws)
    await db_session.flush()
    if _TEST_USER is not None:
        member = WorkspaceMember(
            workspace_id=ws.id,
            user_id=str(_TEST_USER.id),
            email=_TEST_USER.email,
            role=WorkspaceRole.OWNER,
        )
        db_session.add(member)
        await db_session.flush()
    return ws


async def _make_draft_policy(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    name: str = "Content Guidelines",
    guidelines: list | None = None,
) -> dict:
    body: dict = {"name": name, "description": "Phase 2 test policy"}
    if guidelines is not None:
        body["guidelines"] = guidelines
    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies",
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _add_guideline(client: AsyncClient, workspace_id: uuid.UUID, policy_id: str) -> dict:
    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies/{policy_id}/guidelines",
        json=BASE_GUIDELINE,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _activate(client: AsyncClient, workspace_id: uuid.UUID, policy_id: str) -> dict:
    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies/{policy_id}/activate",
        json={"confirm": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Policy creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_policy_returns_201_and_draft(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    policy = await _make_draft_policy(client, ws.id)

    assert policy["status"] == "draft"
    assert policy["version"] == 1
    assert policy["workspace_id"] == str(ws.id)
    assert policy["created_by_id"] == str(_TEST_USER.id)
    assert policy["guideline_count"] == 0


@pytest.mark.asyncio
async def test_create_policy_with_inline_guidelines(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    policy = await _make_draft_policy(client, ws.id, guidelines=[BASE_GUIDELINE])

    assert policy["guideline_count"] == 1
    assert len(policy["guidelines"]) == 1
    assert policy["guidelines"][0]["category"] == "brand_voice"


@pytest.mark.asyncio
async def test_create_policy_unknown_workspace_returns_404(client: AsyncClient):
    fake_id = uuid.uuid4()
    r = await client.post(
        f"/api/v1/workspaces/{fake_id}/policies",
        json={"name": "Ghost Policy"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_policy_blank_name_returns_422(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies",
        json={"name": "   "},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_policy_duplicate_name_version_returns_409(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    await _make_draft_policy(client, ws.id, name="Unique Policy")
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies",
        json={"name": "Unique Policy"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 409
    assert "error" in r.json()


# ---------------------------------------------------------------------------
# Policy listing and retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_policies_returns_paginated_results(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    await _make_draft_policy(client, ws.id, name="Policy Alpha")
    await _make_draft_policy(client, ws.id, name="Policy Beta")

    r = await client.get(f"/api/v1/workspaces/{ws.id}/policies")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_policies_filter_by_status(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    r_active = await client.get(f"/api/v1/workspaces/{ws.id}/policies", params={"status": "active"})
    r_draft = await client.get(f"/api/v1/workspaces/{ws.id}/policies", params={"status": "draft"})
    assert r_active.json()["total"] == 1
    assert r_draft.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_policy_detail_includes_guidelines(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])

    r = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{p['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["guideline_count"] == 1
    assert len(data["guidelines"]) == 1


@pytest.mark.asyncio
async def test_get_policy_nonexistent_returns_404(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    r = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cross-workspace protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_workspace_access_returns_404(client: AsyncClient, db_session: AsyncSession):
    """A policy belonging to workspace A must return 404 when requested via workspace B."""
    ws_a = await _make_workspace(db_session, name="Corp A")
    ws_b = await _make_workspace(db_session, name="Corp B")

    policy_a = await _make_draft_policy(client, ws_a.id, name="Corp A Policy")

    # Attempt to access policy_a via workspace_b — must return 404, not 403 or 200
    r = await client.get(f"/api/v1/workspaces/{ws_b.id}/policies/{policy_a['id']}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Metadata update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_draft_policy_metadata(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id, name="Old Name")

    r = await client.patch(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}",
        json={"name": "New Name"},
        headers={"X-Actor-ID": "editor"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_active_policy_returns_422(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    r = await client.patch(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}",
        json={"name": "Sneaky Update"},
        headers={"X-Actor-ID": "editor"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_requires_guideline(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/activate",
        json={"confirm": True},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422
    assert "guideline" in r.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_activate_requires_confirm_true(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/activate",
        json={"confirm": False},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_activate_draft_with_guideline_succeeds(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])

    r_activate = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/activate",
        json={"confirm": True},
        headers={"X-Actor-ID": "actor"},
    )
    assert r_activate.status_code == 200
    assert r_activate.json()["status"] == "active"


@pytest.mark.asyncio
async def test_activate_auto_deprecates_previous_active_version(
    client: AsyncClient, db_session: AsyncSession
):
    """When a new version is activated, the previously active version is deprecated."""
    ws = await _make_workspace(db_session)

    # Create and activate v1
    p_v1 = await _make_draft_policy(client, ws.id, name="Brand Guide")
    await _add_guideline(client, ws.id, p_v1["id"])
    await _activate(client, ws.id, p_v1["id"])

    # Fork v2 and activate it
    r_fork = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p_v1['id']}/versions",
        headers={"X-Actor-ID": "actor"},
    )
    assert r_fork.status_code == 201
    p_v2 = r_fork.json()
    await _activate(client, ws.id, p_v2["id"])

    # v1 should now be deprecated
    r_v1 = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{p_v1['id']}")
    assert r_v1.json()["status"] == "deprecated"

    # v2 should be active
    r_v2 = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{p_v2['id']}")
    assert r_v2.json()["status"] == "active"


@pytest.mark.asyncio
async def test_deprecate_active_policy_requires_reason(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    # Missing reason (blank)
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/deprecate",
        json={"reason": "   "},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_deprecate_active_policy_succeeds(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/deprecate",
        json={"reason": "Superseded by v2"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "deprecated"


@pytest.mark.asyncio
async def test_invalid_transition_draft_to_deprecated_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    """DRAFT → DEPRECATED is not a valid transition."""
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/deprecate",
        json={"reason": "Skip activation"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422
    assert "Cannot transition" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_archive_terminal_state_blocks_further_transitions(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    # Archive directly from DRAFT (allowed)
    r_archive = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/archive",
        headers={"X-Actor-ID": "actor"},
    )
    assert r_archive.status_code == 200
    assert r_archive.json()["status"] == "archived"

    # Further actions should fail with 422
    r_fail = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/activate",
        json={"confirm": True},
        headers={"X-Actor-ID": "actor"},
    )
    assert r_fail.status_code == 422
    assert "terminal" in r_fail.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# Version history and forking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_history_returns_all_versions_in_order(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p_v1 = await _make_draft_policy(client, ws.id, name="Style Guide")
    await _add_guideline(client, ws.id, p_v1["id"])
    await _activate(client, ws.id, p_v1["id"])

    await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p_v1['id']}/versions",
        headers={"X-Actor-ID": "actor"},
    )

    r = await client.get(f"/api/v1/workspaces/{ws.id}/policies/history/Style Guide")
    assert r.status_code == 200
    data = r.json()
    assert data["policy_name"] == "Style Guide"
    assert len(data["versions"]) == 2
    assert data["versions"][0]["version"] == 1
    assert data["versions"][1]["version"] == 2


@pytest.mark.asyncio
async def test_fork_from_draft_returns_422(client: AsyncClient, db_session: AsyncSession):
    """Forking must only be allowed from ACTIVE policies."""
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/versions",
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_fork_copies_guidelines(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p_v1 = await _make_draft_policy(client, ws.id, name="Guide With Rules")
    await _add_guideline(client, ws.id, p_v1["id"])
    await _activate(client, ws.id, p_v1["id"])

    r_fork = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p_v1['id']}/versions",
        headers={"X-Actor-ID": "actor"},
    )
    p_v2 = r_fork.json()

    assert p_v2["version"] == 2
    assert p_v2["status"] == "draft"
    assert p_v2["guideline_count"] == 1  # copied from v1


# ---------------------------------------------------------------------------
# Guideline ingestion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_guideline_to_draft_succeeds(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    g = await _add_guideline(client, ws.id, p["id"])

    assert g["category"] == "brand_voice"
    assert g["policy_id"] == p["id"]
    assert g["severity_default"] == "medium"
    assert g["is_mandatory"] is True


@pytest.mark.asyncio
async def test_add_guideline_to_active_policy_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=BASE_GUIDELINE,
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_guideline_validation_rejects_blank_rule_text(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    bad = {**BASE_GUIDELINE, "rule_text": "   "}
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=bad,
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_guideline_validation_rejects_rule_text_same_as_title(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    bad = {**BASE_GUIDELINE, "title": "Use Active Voice", "rule_text": "Use Active Voice"}
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=bad,
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_guideline_validation_rejects_invalid_category(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    bad = {**BASE_GUIDELINE, "category": "not_a_valid_category"}
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=bad,
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_guideline_validation_rejects_blank_example_items(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)

    bad = {**BASE_GUIDELINE, "examples_approved": ["valid example", ""]}
    r = await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=bad,
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_guidelines(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    await _add_guideline(client, ws.id, p["id"])
    g2_body = {
        **BASE_GUIDELINE,
        "category": "terminology",
        "title": "Avoid Jargon",
        "rule_text": "Do not use industry jargon that target audiences would not understand.",
    }
    await client.post(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines",
        json=g2_body,
        headers={"X-Actor-ID": "actor"},
    )

    r = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines")
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_update_guideline_on_draft(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    g = await _add_guideline(client, ws.id, p["id"])

    r = await client.patch(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines/{g['id']}",
        json={"severity_default": "high"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 200
    assert r.json()["severity_default"] == "high"


@pytest.mark.asyncio
async def test_update_guideline_on_active_policy_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    g = await _add_guideline(client, ws.id, p["id"])
    await _activate(client, ws.id, p["id"])

    r = await client.patch(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines/{g['id']}",
        json={"severity_default": "critical"},
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_guideline_from_draft(client: AsyncClient, db_session: AsyncSession):
    ws = await _make_workspace(db_session)
    p = await _make_draft_policy(client, ws.id)
    g = await _add_guideline(client, ws.id, p["id"])

    r = await client.delete(
        f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines/{g['id']}",
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 204

    # Verify guideline is gone
    r_list = await client.get(f"/api/v1/workspaces/{ws.id}/policies/{p['id']}/guidelines")
    assert len(r_list.json()) == 0


@pytest.mark.asyncio
async def test_delete_guideline_cross_policy_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    """A guideline from policy B cannot be deleted via policy A's endpoint."""
    ws = await _make_workspace(db_session)
    p_a = await _make_draft_policy(client, ws.id, name="Policy A")
    p_b = await _make_draft_policy(client, ws.id, name="Policy B")
    g_b = await _add_guideline(client, ws.id, p_b["id"])

    r = await client.delete(
        f"/api/v1/workspaces/{ws.id}/policies/{p_a['id']}/guidelines/{g_b['id']}",
        headers={"X-Actor-ID": "actor"},
    )
    assert r.status_code == 404
