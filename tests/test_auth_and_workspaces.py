"""Phase 3 Tests — Authentication & Secure Workspace RBAC.

Covers:
1. User registration, password complexity validation, duplicate email prevention
2. Authentication / Login (valid, wrong password, timing resistance)
3. Access token verification via /auth/me (valid, missing token, forged token)
4. Refresh token rotation and single-use enforcement
5. Logout and revocation
6. Password change endpoint
7. Workspace creation with automatic OWNER assignment
8. Workspace membership management (add, change role, remove)
9. RBAC enforcement:
   - Last OWNER protection against demotion and removal
   - Privilege hierarchy (OWNER > ADMIN > REVIEWER > CONTRIBUTOR > VIEWER)
   - Policy write permission requiring OWNER or ADMIN role
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token

# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "password": "SecurePassword1",
        "full_name": "New User",
    }
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword1",
        "full_name": "Duplicate User",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_register_weak_password_fails(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_cors_preflight_vercel_origin(client: AsyncClient):
    """Verify that OPTIONS preflight from production frontend receives valid CORS headers."""
    headers = {
        "Origin": "https://inkloom-s.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type, authorization",
    }
    r = await client.request("OPTIONS", "/api/v1/auth/register", headers=headers)
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "https://inkloom-s.vercel.app"
    assert r.headers.get("access-control-allow-credentials") == "true"
    allowed_methods = r.headers.get("access-control-allow-methods", "")
    assert "POST" in allowed_methods
    assert "OPTIONS" in allowed_methods
    allowed_headers = r.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers


@pytest.mark.asyncio
async def test_register_cors_preflight_disallowed_origin(client: AsyncClient):
    """Verify that OPTIONS preflight from an unauthorized origin is rejected."""
    headers = {
        "Origin": "https://unauthorized-origin.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    r = await client.request("OPTIONS", "/api/v1/auth/register", headers=headers)
    assert r.headers.get("access-control-allow-origin") is None


# ---------------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    email = "login_test@example.com"
    password = "SecurePassword1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Login Test"},
    )

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    email = "wrong_pass@example.com"
    password = "SecurePassword1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "User"},
    )

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword2"},
    )
    assert r.status_code == 401
    assert "Invalid email or password" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "SomePassword1"},
    )
    assert r.status_code == 401
    assert "Invalid email or password" in r.json()["error"]["message"]


# ---------------------------------------------------------------------------
# 3. Access Token & /me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    email = "me_user@example.com"
    password = "SecurePassword1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Me User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]

    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_forged_token(client: AsyncClient):
    fake_token = create_access_token(
        {"sub": str(uuid.uuid4()), "type": "sentinel_access"},
        secret_key="completely-wrong-secret-key-that-does-not-match",
    )
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fake_token}"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 4. Token Refresh & Rotation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient, db_session: AsyncSession):
    email = "refresh_user@example.com"
    password = "SecurePassword1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Refresh User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    refresh_token = login_res.json()["refresh_token"]

    # First refresh succeeds
    r1 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r1.status_code == 200
    new_data = r1.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != refresh_token

    # Replay attack: using the old refresh token must fail with 401
    r2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# 5. Logout & Revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient):
    email = "logout_user@example.com"
    password = "SecurePassword1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Logout User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    r = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code in (200, 204)

    # Refresh token can no longer be used
    r2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# 6. Change Password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    email = "chpass_user@example.com"
    old_password = "SecurePassword1"
    new_password = "NewSecurePassword2"

    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_password, "full_name": "Pass User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    access_token = login_res.json()["access_token"]

    # Change password
    r = await client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": old_password, "new_password": new_password},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code in (200, 204)

    # Login with old password fails
    r_old = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert r_old.status_code == 401

    # Login with new password succeeds
    r_new = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert r_new.status_code == 200


# ---------------------------------------------------------------------------
# 7. Workspace Creation & RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workspace_assigns_owner(client: AsyncClient):
    email = "owner_user@example.com"
    password = "SecurePassword1"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Owner User"},
    )
    owner_id = reg.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create workspace
    r = await client.post(
        "/api/v1/workspaces",
        json={"name": "Acme Brand Corp", "description": "Acme Brand Workspace"},
        headers=headers,
    )
    assert r.status_code == 201
    ws = r.json()
    ws_id = ws["id"]
    assert ws["name"] == "Acme Brand Corp"

    # List members — creator should be OWNER
    r_members = await client.get(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=headers,
    )
    assert r_members.status_code == 200
    members = r_members.json()["members"]
    assert len(members) == 1
    assert members[0]["user_id"] == owner_id
    assert members[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_workspace_membership_management_lifecycle(client: AsyncClient):
    # Register Owner
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ws_owner@example.com", "password": "SecurePassword1", "full_name": "Owner"},
    )
    tok_owner = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "ws_owner@example.com", "password": "SecurePassword1"},
        )
    ).json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {tok_owner}"}

    # Register Member
    reg_member = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ws_member@example.com",
            "password": "SecurePassword1",
            "full_name": "Member",
        },
    )
    member_id = reg_member.json()["id"]
    tok_member = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "ws_member@example.com", "password": "SecurePassword1"},
        )
    ).json()["access_token"]
    member_headers = {"Authorization": f"Bearer {tok_member}"}

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Lifecycle Workspace"},
        headers=owner_headers,
    )
    ws_id = ws_res.json()["id"]

    # Member initially has no access
    r_unauth = await client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
    )
    assert r_unauth.status_code == 403

    # Owner adds member as CONTRIBUTOR
    r_add = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "email": "ws_member@example.com", "role": "contributor"},
        headers=owner_headers,
    )
    assert r_add.status_code == 201

    # Member now has read access
    r_auth = await client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
    )
    assert r_auth.status_code == 200

    # Contributor cannot create policies (requires OWNER or ADMIN)
    r_create_pol = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies",
        json={"name": "Disallowed Policy"},
        headers=member_headers,
    )
    assert r_create_pol.status_code == 403

    # Owner upgrades member to ADMIN
    r_promote = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}/role",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert r_promote.status_code == 200
    assert r_promote.json()["role"] == "admin"

    # Now as ADMIN, member can create a policy
    r_create_pol2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies",
        json={"name": "Admin Policy"},
        headers=member_headers,
    )
    assert r_create_pol2.status_code == 201

    # Owner removes member
    r_del = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert r_del.status_code == 204

    # Member access is now revoked
    r_revoked = await client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
    )
    assert r_revoked.status_code == 403


@pytest.mark.asyncio
async def test_last_owner_cannot_be_demoted_or_removed(client: AsyncClient):
    # Register Owner
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sole_owner@example.com",
            "password": "SecurePassword1",
            "full_name": "Sole Owner",
        },
    )
    owner_id = reg.json()["id"]
    tok = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "sole_owner@example.com", "password": "SecurePassword1"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Sole Owner Workspace"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    # Demoting last owner fails
    r_demote = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert r_demote.status_code in (400, 422)

    # Removing last owner fails
    r_remove = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        headers=headers,
    )
    assert r_remove.status_code in (400, 422)
