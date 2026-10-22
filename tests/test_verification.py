"""Phase 5 Tests — Deterministic Brand Compliance Engine.

Comprehensive backend tests covering:
1. Rule evaluation correctness for all supported rule types:
   - Prohibited terms (case-sensitive and case-insensitive matching, exact spans).
   - Required terms (missing vs present).
   - Exact brand-name spelling (casing/spelling deviations flagged, exact match passes).
   - Length limits (word count and character count min/max).
2. Clean passes when content complies with all active guidelines.
3. Multiple violations detected across guidelines in a single revision.
4. Determinism: identical input content and guideline configurations produce identical findings.
5. Rejection of non-ACTIVE policies (DRAFT, DEPRECATED, ARCHIVED rejected with 422).
6. Policy version binding and historical immutability (new policy version does not mutate past runs).
7. Workspace boundary enforcement (cross-workspace submission/policy/run access blocked with 404).
8. Role-based authorization (CONTRIBUTOR/REVIEWER/ADMIN/OWNER can run; VIEWER and non-member cannot).
9. Audit trail logging (verification_started and verification_completed events without raw content).
10. Verification run listing, pagination, and single run detail retrieval.
"""

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
    client: AsyncClient, headers: dict, name: str = "Brand Verification Corp"
) -> str:
    """Create a workspace and return its workspace_id."""
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Workspace for verification tests"},
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


async def _create_active_policy(
    client: AsyncClient,
    headers: dict,
    workspace_id: str,
    name: str = "Brand Guidelines",
    guidelines: list | None = None,
) -> str:
    """Create a policy with guidelines and activate it, returning policy_id."""
    if guidelines is None:
        guidelines = [
            {
                "category": "brand_voice",
                "title": "Prohibited Buzzwords",
                "rule_text": "Do not use the word synergy or disruptive in press releases.",
                "severity_default": "high",
                "is_mandatory": True,
                "rule_config": {
                    "rule_type": "prohibited_terms",
                    "terms": ["synergy", "disruptive"],
                    "case_sensitive": False,
                },
            }
        ]

    create_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policies",
        json={"name": name, "description": "Verification test policy", "guidelines": guidelines},
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


async def _create_submission(
    client: AsyncClient,
    headers: dict,
    workspace_id: str,
    content_text: str,
    title: str = "Launch Post",
) -> str:
    """Create a submission and return submission_id."""
    payload = {
        "title": title,
        "campaign_tag": "q4-launch",
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


# ---------------------------------------------------------------------------
# 1. Supported Deterministic Rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prohibited_terms_rule_case_sensitive_and_insensitive(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "prohibited_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "regulatory_compliance",
            "title": "Disallow Unlimited Guarantee",
            "rule_text": "Terms like 'guaranteed profit' are strictly forbidden.",
            "severity_default": "critical",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "prohibited_terms",
                "terms": ["guaranteed profit"],
                "case_sensitive": False,
            },
        },
        {
            "category": "brand_voice",
            "title": "Strict Case Acronym Check",
            "rule_text": "Disallow 'NOOB' in uppercase specifically.",
            "severity_default": "medium",
            "is_mandatory": False,
            "rule_config": {
                "rule_type": "prohibited_terms",
                "terms": ["NOOB"],
                "case_sensitive": True,
            },
        },
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    content = "We offer a Guaranteed Profit with zero risk for every noob in trading."
    sub_id = await _create_submission(client, headers, ws_id, content)

    run_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert run_res.status_code == 201, run_res.text
    data = run_res.json()
    assert data["status"] == "completed"
    assert data["total_rules"] == 2
    assert data["violation_count"] == 1
    assert data["passed_rules"] == 1

    finding = data["findings"][0]
    assert "guaranteed profit" in finding["message"].lower()
    assert finding["severity"] == "critical"
    # Exact character span accuracy
    start = finding["char_start"]
    end = finding["char_end"]
    assert content[start:end].lower() == "guaranteed profit"
    # Evidence reference attached
    assert len(finding["evidence_references"]) == 1
    assert finding["evidence_references"][0]["reference_type"] == "policy_clause"


@pytest.mark.asyncio
async def test_required_terms_rule(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "req_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "regulatory_compliance",
            "title": "Mandatory FDA Disclaimer",
            "rule_text": "Marketing statements must contain 'Terms and conditions apply'.",
            "severity_default": "high",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "required_terms",
                "terms": ["Terms and conditions apply."],
                "case_sensitive": False,
            },
        }
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    # 1. Missing required phrase -> should fail
    sub_fail = await _create_submission(client, headers, ws_id, "Buy our miracle product today!")
    res_fail = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_fail}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res_fail.status_code == 201
    assert res_fail.json()["violation_count"] == 1
    assert "Required term missing" in res_fail.json()["findings"][0]["message"]

    # 2. Present required phrase -> should pass
    sub_pass = await _create_submission(
        client, headers, ws_id, "Buy our product today! Terms and conditions apply."
    )
    res_pass = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_pass}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res_pass.status_code == 201
    assert res_pass.json()["violation_count"] == 0
    assert res_pass.json()["passed_rules"] == 1


@pytest.mark.asyncio
async def test_brand_spelling_rule(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "spelling_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "brand_voice",
            "title": "Canonical Brand Spelling",
            "rule_text": "Our brand must always be written as 'Inkloom' with exact capitalization.",
            "severity_default": "medium",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "brand_spelling",
                "canonical_name": "Inkloom",
            },
        }
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    # Content with misspelled/mis-cased variants: 'inkloom' and 'INKLOOM'
    content = "Welcome to inkloom! At INKLOOM, we prioritize precision."
    sub_id = await _create_submission(client, headers, ws_id, content)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["violation_count"] == 2
    for finding in data["findings"]:
        assert "Brand name misspelled" in finding["message"]
        assert "Inkloom" in finding["recommendation"]
        s, e = finding["char_start"], finding["char_end"]
        assert content[s:e] in ["inkloom", "INKLOOM"]

    # Correct spelling passes cleanly
    correct_content = "Welcome to Inkloom! At Inkloom, we build trust."
    sub_ok = await _create_submission(client, headers, ws_id, correct_content)
    res_ok = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_ok}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["violation_count"] == 0
    assert res_ok.json()["passed_rules"] == 1


@pytest.mark.asyncio
async def test_length_limit_rule_words_and_chars(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "length_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "brand_voice",
            "title": "Social Post Word Limit",
            "rule_text": "Post must be between 5 and 15 words.",
            "severity_default": "low",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "length_limit",
                "unit": "words",
                "min_count": 5,
                "max_count": 15,
            },
        }
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    # Too short (3 words)
    sub_short = await _create_submission(client, headers, ws_id, "Too short text.")
    r_short = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_short}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_short.status_code == 201
    assert r_short.json()["violation_count"] == 1
    assert "below minimum" in r_short.json()["findings"][0]["message"]

    # In range (8 words)
    sub_ok = await _create_submission(
        client, headers, ws_id, "One two three four five six seven eight."
    )
    r_ok = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_ok}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_ok.status_code == 201
    assert r_ok.json()["violation_count"] == 0

    # Too long (18 words)
    sub_long = await _create_submission(
        client,
        headers,
        ws_id,
        "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen.",
    )
    r_long = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_long}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_long.status_code == 201
    assert r_long.json()["violation_count"] == 1
    assert "exceeds maximum" in r_long.json()["findings"][0]["message"]


# ---------------------------------------------------------------------------
# 2. Clean Pass & Multiple Violations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clean_pass_verification(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "clean_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "regulatory_compliance",
            "title": "No False Claims",
            "rule_text": "Do not claim cure-all capabilities.",
            "severity_default": "high",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "prohibited_terms",
                "terms": ["cure-all", "miracle"],
                "case_sensitive": False,
            },
        },
        {
            "category": "brand_voice",
            "title": "Include Tagline",
            "rule_text": "Include the tagline 'Empower your craft'.",
            "severity_default": "medium",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "required_terms",
                "terms": ["Empower your craft"],
                "case_sensitive": False,
            },
        },
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    clean_content = "Discover our robust analytics suite. Empower your craft with modern tooling."
    sub_id = await _create_submission(client, headers, ws_id, clean_content)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["total_rules"] == 2
    assert data["passed_rules"] == 2
    assert data["violation_count"] == 0
    assert len(data["findings"]) == 0


@pytest.mark.asyncio
async def test_multiple_guidelines_and_violations(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "multi_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "regulatory_compliance",
            "title": "Prohibited Claims",
            "rule_text": "No miracle guarantees.",
            "severity_default": "critical",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "prohibited_terms",
                "terms": ["miracle", "100% free"],
                "case_sensitive": False,
            },
        },
        {
            "category": "brand_voice",
            "title": "Brand Name Exact",
            "rule_text": "Brand is Sentinel.",
            "severity_default": "high",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "brand_spelling",
                "canonical_name": "Sentinel",
            },
        },
        {
            "category": "brand_voice",
            "title": "Required Copyright",
            "rule_text": "Must include All rights reserved.",
            "severity_default": "low",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "required_terms",
                "terms": ["All rights reserved"],
                "case_sensitive": False,
            },
        },
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)

    # Content violates all 3 rules:
    # 1. contains "miracle" and "100% free" (2 prohibited violations)
    # 2. contains "sentinel" in lowercase (1 spelling violation)
    # 3. missing "All rights reserved" (1 required term violation)
    content = "This miracle product is 100% free from sentinel today!"
    sub_id = await _create_submission(client, headers, ws_id, content)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["total_rules"] == 3
    assert data["passed_rules"] == 0
    assert data["violation_count"] == 4
    assert len(data["findings"]) == 4


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_execution_produces_identical_results(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "determ_author@example.com")
    ws_id = await _create_workspace(client, headers)

    guidelines = [
        {
            "category": "brand_voice",
            "title": "Check Buzzwords",
            "rule_text": "Ban buzzwords like revolutionize.",
            "severity_default": "medium",
            "is_mandatory": True,
            "rule_config": {
                "rule_type": "prohibited_terms",
                "terms": ["revolutionize"],
                "case_sensitive": False,
            },
        }
    ]
    policy_id = await _create_active_policy(client, headers, ws_id, guidelines=guidelines)
    content = "Our tool will revolutionize your marketing workflow completely."
    sub_id = await _create_submission(client, headers, ws_id, content)

    # Run 1
    r1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r1.status_code == 201
    d1 = r1.json()

    # Run 2
    r2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r2.status_code == 201
    d2 = r2.json()

    # IDs of runs differ
    assert d1["id"] != d2["id"]
    # Deterministic metrics match exactly
    assert d1["total_rules"] == d2["total_rules"] == 1
    assert d1["passed_rules"] == d2["passed_rules"] == 0
    assert d1["violation_count"] == d2["violation_count"] == 1

    f1 = d1["findings"][0]
    f2 = d2["findings"][0]
    assert f1["message"] == f2["message"]
    assert f1["char_start"] == f2["char_start"]
    assert f1["char_end"] == f2["char_end"]
    assert f1["flagged_excerpt"] == f2["flagged_excerpt"]
    assert f1["recommendation"] == f2["recommendation"]


# ---------------------------------------------------------------------------
# 4. Policy Lifecycle & Status Rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_draft_deprecated_archived_policies(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "lifecycle_author@example.com")
    ws_id = await _create_workspace(client, headers)

    sub_id = await _create_submission(client, headers, ws_id, "Sample content for testing.")

    # 1. DRAFT policy
    draft_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies",
        json={
            "name": "Draft Policy",
            "guidelines": [
                {
                    "category": "brand_voice",
                    "title": "Rule 1",
                    "rule_text": "Substantive rule text for guideline",
                    "severity_default": "low",
                    "is_mandatory": True,
                    "rule_config": {"rule_type": "prohibited_terms", "terms": ["bad"]},
                }
            ],
        },
        headers=headers,
    )
    draft_id = draft_res.json()["id"]

    # Attempt verification against DRAFT -> 422
    r_draft = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": draft_id},
        headers=headers,
    )
    assert r_draft.status_code == 422
    assert "Only ACTIVE policies may be used" in r_draft.json()["error"]["message"]

    # Activate it so we can deprecate and archive
    await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{draft_id}/activate",
        json={"confirm": True},
        headers=headers,
    )

    # 2. DEPRECATED policy
    dep_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{draft_id}/deprecate",
        json={"reason": "Superseded by updated policy guidelines"},
        headers=headers,
    )
    assert dep_res.status_code == 200, dep_res.text
    r_dep = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": draft_id},
        headers=headers,
    )
    assert r_dep.status_code == 422
    assert "deprecated" in r_dep.json()["error"]["message"].lower()

    # 3. ARCHIVED policy
    arch_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{draft_id}/archive",
        headers=headers,
    )
    assert arch_res.status_code == 200, arch_res.text
    r_arch = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": draft_id},
        headers=headers,
    )
    assert r_arch.status_code == 422
    assert "archived" in r_arch.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 5. Policy Version Binding & Historical Immutability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_version_binding_and_immutability(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "version_author@example.com")
    ws_id = await _create_workspace(client, headers)

    # Version 1 policy
    g1 = [
        {
            "category": "brand_voice",
            "title": "V1 Rule",
            "rule_text": "Forbidden word foo in v1.",
            "severity_default": "medium",
            "is_mandatory": True,
            "rule_config": {"rule_type": "prohibited_terms", "terms": ["foo"]},
        }
    ]
    p_v1_id = await _create_active_policy(
        client, headers, ws_id, name="Corporate Policy", guidelines=g1
    )

    content = "This content has foo and bar inside."
    sub_id = await _create_submission(client, headers, ws_id, content)

    # Run against V1
    r_v1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": p_v1_id},
        headers=headers,
    )
    assert r_v1.status_code == 201
    run_v1_id = r_v1.json()["id"]
    assert r_v1.json()["policy_version"] == 1
    assert r_v1.json()["violation_count"] == 1

    # Now create new version of policy (fork from active)
    fork_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{p_v1_id}/versions",
        headers=headers,
    )
    assert fork_res.status_code == 201
    p_v2_id = fork_res.json()["id"]
    assert fork_res.json()["version"] == 2

    # Add extra guideline to v2
    await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{p_v2_id}/guidelines",
        json={
            "category": "brand_voice",
            "title": "V2 Rule",
            "rule_text": "Forbidden word bar in v2.",
            "severity_default": "high",
            "is_mandatory": True,
            "rule_config": {"rule_type": "prohibited_terms", "terms": ["bar"]},
        },
        headers=headers,
    )

    # Activate V2 (which auto-deprecates V1)
    await client.post(
        f"/api/v1/workspaces/{ws_id}/policies/{p_v2_id}/activate",
        json={"confirm": True},
        headers=headers,
    )

    # Run verification against V2
    r_v2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": p_v2_id},
        headers=headers,
    )
    assert r_v2.status_code == 201
    assert r_v2.json()["policy_version"] == 2
    assert r_v2.json()["violation_count"] == 2  # flags both 'foo' and 'bar'

    # Retrieve historic V1 run — must remain completely unchanged!
    hist_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs/{run_v1_id}",
        headers=headers,
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["id"] == run_v1_id
    assert hist_data["policy_version"] == 1
    assert hist_data["violation_count"] == 1


# ---------------------------------------------------------------------------
# 6. Workspace Boundary Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_workspace_isolation_and_404(client: AsyncClient):
    _, headers_a = await _create_user_and_headers(client, "user_a@example.com")
    ws_a = await _create_workspace(client, headers_a, name="Workspace Alpha")

    _, headers_b = await _create_user_and_headers(client, "user_b@example.com")
    ws_b = await _create_workspace(client, headers_b, name="Workspace Beta")

    # Policy in WS A
    policy_a = await _create_active_policy(client, headers_a, ws_a)
    # Submission in WS A
    sub_a = await _create_submission(client, headers_a, ws_a, "Alpha content.")

    # Policy in WS B
    policy_b = await _create_active_policy(client, headers_b, ws_b)

    # 1. User A tries to verify Alpha submission against Beta's policy -> 404
    r_cross_pol = await client.post(
        f"/api/v1/workspaces/{ws_a}/submissions/{sub_a}/verification/runs?revision_number=1",
        json={"policy_id": policy_b},
        headers=headers_a,
    )
    assert r_cross_pol.status_code == 404

    # 2. Run legitimate verification in WS A
    r_run = await client.post(
        f"/api/v1/workspaces/{ws_a}/submissions/{sub_a}/verification/runs?revision_number=1",
        json={"policy_id": policy_a},
        headers=headers_a,
    )
    assert r_run.status_code == 201
    run_id = r_run.json()["id"]

    # 3. User B tries to read Alpha's run via WS B endpoint -> 404
    r_cross_read = await client.get(
        f"/api/v1/workspaces/{ws_b}/submissions/{sub_a}/verification/runs/{run_id}",
        headers=headers_b,
    )
    assert r_cross_read.status_code == 404

    # 4. User B tries to access Alpha workspace directly -> 403 (non-member)
    r_cross_ws = await client.get(
        f"/api/v1/workspaces/{ws_a}/submissions/{sub_a}/verification/runs/{run_id}",
        headers=headers_b,
    )
    assert r_cross_ws.status_code in (403, 404)


# ---------------------------------------------------------------------------
# 7. Role-Based Authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_authorization_roles(client: AsyncClient):
    owner_id, owner_headers = await _create_user_and_headers(client, "owner_rbac@example.com")
    ws_id = await _create_workspace(client, owner_headers)
    policy_id = await _create_active_policy(client, owner_headers, ws_id)
    sub_id = await _create_submission(client, owner_headers, ws_id, "Sample content.")

    # Create users with different roles
    contrib_id, contrib_headers = await _create_user_and_headers(client, "contrib_rbac@example.com")
    await _add_member(
        client, owner_headers, ws_id, contrib_id, "contrib_rbac@example.com", role="contributor"
    )

    viewer_id, viewer_headers = await _create_user_and_headers(client, "viewer_rbac@example.com")
    await _add_member(
        client, owner_headers, ws_id, viewer_id, "viewer_rbac@example.com", role="viewer"
    )

    # 1. Contributor can run verification -> 201
    r_contrib = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=contrib_headers,
    )
    assert r_contrib.status_code == 201
    run_id = r_contrib.json()["id"]

    # 2. Viewer CANNOT run verification -> 403 Forbidden
    r_viewer = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=viewer_headers,
    )
    assert r_viewer.status_code == 403

    # 3. Viewer CAN view runs and run details -> 200 OK
    r_view_list = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs",
        headers=viewer_headers,
    )
    assert r_view_list.status_code == 200
    assert r_view_list.json()["total"] >= 1

    r_view_detail = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs/{run_id}",
        headers=viewer_headers,
    )
    assert r_view_detail.status_code == 200
    assert r_view_detail.json()["id"] == run_id


# ---------------------------------------------------------------------------
# 8. Audit Trail Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_logging_for_verification(client: AsyncClient, db_session: AsyncSession):
    user_id, headers = await _create_user_and_headers(client, "audit_verify_actor@example.com")
    ws_id = await _create_workspace(client, headers)
    policy_id = await _create_active_policy(client, headers, ws_id)
    content = "Exclusive launch text for verification audit test."
    sub_id = await _create_submission(client, headers, ws_id, content)

    run_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert run_res.status_code == 201
    run_id = run_res.json()["id"]

    # Query audit logs from db
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == uuid.UUID(ws_id),
            AuditEvent.event_type.in_(
                [AuditEventType.VERIFICATION_STARTED, AuditEventType.VERIFICATION_COMPLETED]
            ),
        )
        .order_by(AuditEvent.occurred_at.asc())
    )
    events = list((await db_session.execute(stmt)).scalars().all())
    assert len(events) >= 2

    start_event = next(e for e in events if e.event_type == AuditEventType.VERIFICATION_STARTED)
    assert start_event.actor_id == user_id
    assert "policy_id" in start_event.event_payload
    # Ensure raw content is NOT leaked in audit logs
    assert content not in str(start_event.event_payload)

    completed_event = next(
        e for e in events if e.event_type == AuditEventType.VERIFICATION_COMPLETED
    )
    assert completed_event.actor_id == user_id
    assert completed_event.resource_id == run_id
    assert "total_rules" in completed_event.event_payload
    assert "violation_count" in completed_event.event_payload
    assert content not in str(completed_event.event_payload)


# ---------------------------------------------------------------------------
# 9. List Runs, Filter by Revision, and Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_verification_runs_and_pagination_and_filter(client: AsyncClient):
    _, headers = await _create_user_and_headers(client, "list_author@example.com")
    ws_id = await _create_workspace(client, headers)
    policy_id = await _create_active_policy(client, headers, ws_id)

    # Create submission (Revision 1)
    sub_id = await _create_submission(client, headers, ws_id, "Revision 1 text.")

    # Create Revision 2 on same submission
    rev2_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/revisions",
        json={"content_text": "Revision 2 updated text.", "change_summary": "Update copy"},
        headers=headers,
    )
    assert rev2_res.status_code == 201
    assert rev2_res.json()["revision_number"] == 2

    # Run verification on revision 1
    r_rev1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_rev1.status_code == 201

    # Run verification twice on revision 2
    r_rev2_a = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=2",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_rev2_a.status_code == 201

    r_rev2_b = await client.post(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=2",
        json={"policy_id": policy_id},
        headers=headers,
    )
    assert r_rev2_b.status_code == 201

    # 1. List all runs for submission (should be 3)
    list_all = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs",
        headers=headers,
    )
    assert list_all.status_code == 200
    assert list_all.json()["total"] == 3
    assert len(list_all.json()["items"]) == 3

    # 2. Filter by revision_number=1 (should be 1)
    list_rev1 = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=1",
        headers=headers,
    )
    assert list_rev1.status_code == 200
    assert list_rev1.json()["total"] == 1

    # 3. Filter by revision_number=2 (should be 2)
    list_rev2 = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?revision_number=2",
        headers=headers,
    )
    assert list_rev2.status_code == 200
    assert list_rev2.json()["total"] == 2

    # 4. Pagination
    paged = await client.get(
        f"/api/v1/workspaces/{ws_id}/submissions/{sub_id}/verification/runs?page=1&page_size=2",
        headers=headers,
    )
    assert paged.status_code == 200
    pdata = paged.json()
    assert pdata["total"] == 3
    assert len(pdata["items"]) == 2
    assert pdata["has_next"] is True
