# Inkloom Sentinel — Full-Stack Brand Governance Platform

**Inkloom Sentinel** is an evidence-backed AI brand-governance platform designed to verify marketing and corporate content against versioned brand guidelines and regulatory policies before public release.

This repository contains the complete multi-phase implementation: foundational domain models, full REST API (authentication, workspaces, policies, submissions, verification, evidence, semantic review, corrections, audit analytics), and a React/TypeScript frontend dashboard.

---

## Architecture Overview

A modular, decoupled backend built on **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.0 (Async)**, **Pydantic v2**, and **Alembic**, fronted by a **React 18 + TypeScript + Vite + Tailwind CSS** single-page application.

```
├── alembic/                    # Database migration environment & versions
│   ├── env.py                  # Async Alembic runtime configuration
│   └── versions/               # Sequential migration scripts (Phases 1-8)
├── app/
│   ├── api/                    # API presentation layer
│   │   ├── dependencies.py     # Injectable route dependencies (DB, auth, services)
│   │   ├── middleware.py       # Request ID tracing & timing headers
│   │   └── v1/                 # API Version 1 namespace
│   │       ├── endpoints/
│   │       │   ├── auth.py         # Register, login, refresh, logout, me, change-password
│   │       │   ├── workspaces.py   # Workspace CRUD & RBAC membership management
│   │       │   ├── policies.py     # Brand policy lifecycle + guideline management
│   │       │   ├── submissions.py  # Content submissions & immutable revision history
│   │       │   ├── verification.py # Deterministic rule-engine verification runs
│   │       │   ├── evidence.py     # Evidence sources & claim assessment
│   │       │   ├── semantic.py     # Semantic review engine runs
│   │       │   ├── reviews.py      # Unified review summary, corrections, decisions
│   │       │   ├── audit.py        # Audit timeline, provenance & governance analytics
│   │       │   ├── health.py       # Liveness, readiness, detailed health
│   │       │   └── info.py         # Platform metadata
│   │       └── router.py           # Master v1 router aggregation
│   ├── core/                   # Platform infrastructure & cross-cutting concerns
│   │   ├── config.py           # Environment-based Pydantic settings & validation
│   │   ├── database.py         # Async engine, sessionmaker, and health probes
│   │   ├── errors.py           # Standardized RFC 7807 compatible error envelope
│   │   ├── logging.py          # Structured logging with credential redaction
│   │   ├── rate_limit.py       # In-process sliding-window rate limiter
│   │   ├── security.py         # bcrypt, HS256 JWT, refresh token hashing, HMAC
│   │   └── ssrf.py             # SSRF protection for external evidence URL fetching
│   ├── domain/                 # Core domain entities & boundaries
│   │   ├── enums.py            # All domain enumerations & lifecycle states
│   │   ├── models/             # SQLAlchemy 2.0 declarative database entities
│   │   │   ├── base.py         # DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│   │   │   ├── user.py         # User, RefreshToken
│   │   │   ├── workspace.py    # BrandWorkspace, WorkspaceMember
│   │   │   ├── policy.py       # BrandPolicy, PolicyGuideline
│   │   │   ├── submission.py   # ContentSubmission, ContentRevision
│   │   │   ├── verification.py # VerificationRun, VerificationFinding
│   │   │   ├── evidence.py     # EvidenceSource, ContentClaim, ClaimAssessment
│   │   │   ├── semantic.py     # SemanticReviewRun, SemanticReviewFinding
│   │   │   ├── review.py       # ReviewDecision, CorrectionSuggestion
│   │   │   └── audit.py        # AuditEvent (immutable append-only)
│   │   └── schemas/            # Pydantic v2 DTOs and API contract schemas
│   │       ├── auth.py / workspace.py / policy.py / submission.py
│   │       ├── verification.py / evidence.py / semantic.py / review.py
│   │       └── audit.py / common.py / health.py
│   ├── services/               # Application service layer
│   │   ├── auth_service.py         # JWT auth, bcrypt, token refresh & revocation
│   │   ├── workspace_service.py    # Workspace creation, RBAC enforcement
│   │   ├── policy_service.py       # Policy lifecycle, guideline management, forking
│   │   ├── submission_service.py   # Submission workflow, optimistic concurrency
│   │   ├── verification_service.py # Deterministic rule-engine execution
│   │   ├── claim_service.py        # Evidence source lifecycle, claim assessment
│   │   ├── extraction_service.py   # Claim extraction from revision content
│   │   ├── semantic_service.py     # Semantic review with confidence scoring
│   │   ├── review_service.py       # Unified orchestration, corrections, decisions
│   │   ├── analytics_service.py    # Submission provenance & governance analytics
│   │   └── audit_service.py        # Append-only audit logger with IP hashing
│   └── main.py                 # Application factory & lifespan lifecycle
├── frontend/                   # React 18 + TypeScript + Vite + Tailwind CSS SPA
│   └── src/
│       ├── api/client.ts           # Centralized API client with token refresh
│       ├── context/AuthContext.tsx # Auth state, workspace selection, token mgmt
│       ├── pages/                  # Full application pages (see below)
│       └── components/             # Layout, common, marketing components
├── tests/                      # 153 automated tests (100% pass rate)
├── .env.example                # Safe environment configuration template
├── alembic.ini                 # Database migration tool configuration
└── pyproject.toml              # Project dependencies, tooling & test settings
```

---

## Domain Boundaries

### 1. Authentication & Users (`user.py`, `auth_service.py`)
- `User`: Registered accounts with bcrypt-hashed passwords and active/disabled state.
- `RefreshToken`: Opaque 32-byte tokens — only SHA-256 hash stored server-side.
- JWT access tokens (HS256, 15-minute lifetime) + sliding refresh rotation.
- Login failures return generic messages; email existence is not revealed.

### 2. Brand Workspace & Membership (`workspace.py`)
- `BrandWorkspace`: Tenancy boundary for an organization's brand governance.
- `WorkspaceMember`: Associates users with RBAC roles (`OWNER`, `ADMIN`, `REVIEWER`, `CONTRIBUTOR`, `VIEWER`).
- Last OWNER protection: cannot demote or remove the sole workspace owner.

### 3. Versioned Brand Policies & Guidelines (`policy.py`)
- `BrandPolicy`: Explicitly versioned rule sets with state machine (`DRAFT → ACTIVE → DEPRECATED → ARCHIVED`).
- `PolicyGuideline`: Granular verifiable clauses by category (`BRAND_VOICE`, `TONE_CONSISTENCY`, `REGULATORY_COMPLIANCE`, `TERMINOLOGY`, `FACTUAL_ACCURACY`, `RESTRICTED_CLAIMS`).
- Policy forking: clone an existing policy version to create an incremented draft.
- Activation auto-deprecates the previous active version.

### 4. Content Submissions & Revisions (`submission.py`)
- `ContentSubmission`: Lifecycle state machine (`DRAFT → SUBMITTED → IN_REVIEW → APPROVED/REJECTED/CHANGES_REQUESTED`).
- `ContentRevision`: Sequential, immutable content snapshots with optimistic concurrency guard.

### 5. Deterministic Verification (`verification.py`)
- `VerificationRun`: Rule-engine execution against a revision and active policy.
- `VerificationFinding`: Flagged violations with exact character ranges, severity, and remediation advice.

### 6. Evidence Sources & Claim Assessment (`evidence.py`)
- `EvidenceSource`: Authoritative references with approval lifecycle and SSRF-protected URL validation.
- `ContentClaim`: Extracted factual claims from revision content.
- `ClaimAssessment`: Evidence-backed verdict (`SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, `NEEDS_HUMAN_REVIEW`, `CONFLICTING_EVIDENCE`).

### 7. Semantic Review (`semantic.py`)
- `SemanticReviewRun`: Guideline-by-guideline semantic assessment with overall outcome.
- `SemanticReviewFinding`: Per-guideline outcome (`PASS`, `VIOLATION`, `INCONCLUSIVE`, `NEEDS_REVIEW`) with confidence scoring.

### 8. Unified Review, Corrections & Governance (`review.py`)
- `CorrectionSuggestion`: Structured correction with character offsets, proposed replacement, and evidence citation. Applying creates a new `ContentRevision`.
- `ReviewDecision`: Human governance determinations (`APPROVE`, `REJECT`, `REQUEST_CHANGES`) with separation-of-duties enforcement (authors cannot self-approve).
- Unified Review Summary: Assembles all engines (deterministic + claims + semantic) into a single compliance report. Never reports a clean pass when any check is incomplete.

### 9. Audit & Analytics (`audit.py`)
- `AuditEvent`: Append-only event log protected at the ORM layer against updates and deletes. SHA-256 pseudonymized client IPs.
- Submission provenance: full revision-by-revision trace of verifications, claims, corrections, and decisions.
- Governance analytics: violation counts, guideline rankings, turnaround durations, intervention percentages.

---

## Prerequisites

- **Python**: 3.11 or higher (tested on 3.13)
- **Node.js**: 18+ (for frontend)
- **Database**: SQLite (local dev) or PostgreSQL 14+ (staging/production)

---

## Getting Started

### 1. Environment Configuration

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` and adjust settings. Production requires `ENVIRONMENT=production`, a strong `SECRET_KEY` (32+ chars), and a PostgreSQL `DATABASE_URL`.

### 2. Backend — Database Migrations

```bash
python -m alembic upgrade head
```

### 3. Backend — Local Development Server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **OpenAPI Docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### 4. Frontend — Development Server

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173** and proxies `/api` to the backend.

---

## API Endpoints Reference

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user account |
| `POST` | `/api/v1/auth/login` | Login and receive JWT + refresh token |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token and issue new access token |
| `POST` | `/api/v1/auth/logout` | Revoke current refresh token |
| `GET` | `/api/v1/auth/me` | Get authenticated user profile |
| `POST` | `/api/v1/auth/change-password` | Change account password |

### Workspaces & Membership
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/workspaces` | Create workspace (caller becomes OWNER) |
| `GET` | `/api/v1/workspaces` | List workspaces the user is a member of |
| `GET` | `/api/v1/workspaces/{id}` | Get workspace details |
| `GET` | `/api/v1/workspaces/{id}/members` | List workspace members |
| `POST` | `/api/v1/workspaces/{id}/members` | Add member (OWNER/ADMIN) |
| `PATCH` | `/api/v1/workspaces/{id}/members/{uid}/role` | Change member role (OWNER) |
| `DELETE` | `/api/v1/workspaces/{id}/members/{uid}` | Remove member |

### Brand Policies
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/workspaces/{id}/policies` | Create draft policy |
| `GET` | `/api/v1/workspaces/{id}/policies` | List policies (paginated, filterable) |
| `GET` | `/api/v1/workspaces/{id}/policies/{pid}` | Get policy with guidelines |
| `PATCH` | `/api/v1/workspaces/{id}/policies/{pid}` | Update draft policy metadata |
| `POST` | `/api/v1/workspaces/{id}/policies/{pid}/activate` | Activate draft (requires guideline) |
| `POST` | `/api/v1/workspaces/{id}/policies/{pid}/deprecate` | Deprecate active policy |
| `POST` | `/api/v1/workspaces/{id}/policies/{pid}/archive` | Archive terminal state |
| `POST` | `/api/v1/workspaces/{id}/policies/{pid}/fork` | Fork policy into new draft version |
| `GET` | `/api/v1/workspaces/{id}/policies/{pid}/versions` | Version history |
| `POST/GET/PATCH/DELETE` | `/api/v1/workspaces/{id}/policies/{pid}/guidelines/...` | Guideline management |

### Content Submissions & Revisions
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/workspaces/{id}/submissions` | Create submission |
| `GET` | `/api/v1/workspaces/{id}/submissions` | List submissions |
| `GET/PATCH` | `/api/v1/workspaces/{id}/submissions/{sid}` | Get / update submission |
| `POST` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions` | Create new revision |
| `GET` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions` | List revisions |
| `GET` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}` | Get specific revision |

### Verification, Evidence, Semantic, Review
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/verify` | Run deterministic verification |
| `GET` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/findings` | List verification findings |
| `GET/POST/PATCH` | `/api/v1/workspaces/{id}/evidence/sources/...` | Evidence source lifecycle |
| `POST/GET/PATCH` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/claims/...` | Claim extraction & assessment |
| `POST` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/semantic-review` | Run semantic review |
| `GET` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/review-summary` | **Unified compliance report** |
| `POST/GET/PATCH` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/suggestions/...` | Correction suggestions |
| `POST` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/suggestions/{id}/apply` | Apply correction (creates new revision) |
| `POST/GET` | `/api/v1/workspaces/{id}/submissions/{sid}/revisions/{n}/decisions/...` | Human review decisions |

### Audit & Analytics
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/workspaces/{id}/audit/events` | Audit event timeline (paginated) |
| `GET` | `/api/v1/workspaces/{id}/audit/submissions/{sid}/provenance` | Full submission provenance trace |
| `GET` | `/api/v1/workspaces/{id}/audit/analytics` | Governance analytics dashboard |

### Health & Diagnostics
| Method | Path | Description |
|---|---|---|
| `GET` | `/health/live` | Process liveness probe |
| `GET` | `/health/ready` | Database readiness probe |
| `GET` | `/health` | Comprehensive operational status |

---

## Frontend Pages

| Page | Route | Description |
|---|---|---|
| Landing | `/` | Marketing page with platform overview |
| Login / Signup | `/login`, `/signup` | Authentication flows |
| Dashboard | `/app` | Governance metrics, recent submissions |
| Policies | `/app/policies` | Policy authoring, activation, guideline management |
| Submissions | `/app/submissions` | Content submission & revision workflow |
| Evidence | `/app/evidence` | Evidence source management & claim assessment |
| Reviews | `/app/reviews` | Unified compliance review & correction workflow |
| Audit | `/app/audit` | Audit event timeline |
| Analytics | `/app/analytics` | Governance analytics dashboard |
| Settings | `/app/settings` | Workspace settings, member management |

---

## Automated Testing

**153 tests · 100% pass rate**

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest --cov=app tests/

# Run linting
python -m ruff check .
```

Test coverage spans:
- Configuration validation & production guardrails
- Domain model constraints & ORM-layer immutability
- All API endpoint happy paths, error paths, and RBAC enforcement
- Authentication, JWT validation, token rotation, revocation
- Policy lifecycle state machine transitions
- Submission optimistic concurrency
- Verification rule-engine execution
- Evidence SSRF protection, source lifecycle, claim assessments
- Semantic review confidence scoring
- Unified review orchestration & clean-pass logic
- Correction suggestion application & supersession
- Separation-of-duties enforcement
- Audit event immutability (update/delete prohibited)
- Cross-workspace data isolation
- Governance analytics calculation accuracy

---

## Security Foundation

- **Secrets Isolation**: All secrets read from environment variables; `.gitignore` prevents `.env`, `*.db`, keys from being committed.
- **Production Guardrails**: Config validator rejects `DEBUG=True`, placeholder `SECRET_KEY`, or SQLite when `ENVIRONMENT=production`.
- **Password Security**: bcrypt (12 rounds) — never logged, returned in responses, or stored plaintext.
- **Token Security**: HS256 JWTs (15 min) + opaque refresh tokens (only SHA-256 hash stored).
- **SSRF Protection**: Evidence source URLs validated against blocklists (loopback, private ranges, cloud metadata endpoints).
- **Rate Limiting**: Sliding-window in-process limiter on auth and expensive operations.
- **Sensitive Data Redaction**: Structured logging auto-redacts credentials, bearer tokens, and passwords.
- **Privacy-Preserving Audit**: IP addresses are HMAC-SHA-256 hashed before recording in the audit trail.
- **Separation of Duties**: Submission authors cannot approve their own content.
- **Request Tracing**: All requests carry a unique `X-Request-ID` and latency `X-Process-Time` header.
