# Inkloom Sentinel — Product Foundation (Phase 1)

**Inkloom Sentinel** is an evidence-backed AI brand-governance platform designed to verify marketing and corporate content against versioned brand guidelines and regulatory policies before public release.

This repository contains the Phase 1 foundational architecture, core domain models, configuration layer, database migration pipeline, and API framework.

---

## Architecture Overview

Phase 1 establishes a modular, decoupled backend foundation built on Python 3.11+, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, and Alembic.

```
├── alembic/                    # Database migration environment & versions
│   ├── env.py                  # Async Alembic runtime configuration
│   ├── script.py.mako          # Revision script template
│   └── versions/               # Sequential migration scripts
├── app/
│   ├── api/                    # API presentation layer
│   │   ├── dependencies.py     # Injectable route dependencies (DB, services)
│   │   ├── middleware.py       # Request ID tracing & timing headers
│   │   └── v1/                 # API Version 1 namespace
│   │       ├── endpoints/
│   │       │   ├── health.py   # Liveness, readiness, and detailed health
│   │       │   └── info.py     # Platform metadata
│   │       └── router.py       # Master v1 router aggregation
│   ├── core/                   # Platform infrastructure & cross-cutting concerns
│   │   ├── config.py           # Environment-based Pydantic settings & validation
│   │   ├── database.py         # Async engine, sessionmaker, and health probes
│   │   ├── errors.py           # Standardized RFC 7807 compatible error envelope
│   │   ├── logging.py          # Structured logging with credential redaction
│   │   └── security.py         # Foundational cryptographic & hashing utilities
│   ├── domain/                 # Core domain entities & boundaries
│   │   ├── enums.py            # Standard domain classifications & lifecycles
│   │   ├── models/             # SQLAlchemy 2.0 declarative database entities
│   │   │   ├── base.py         # DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│   │   │   ├── workspace.py    # BrandWorkspace, WorkspaceMember
│   │   │   ├── policy.py       # BrandPolicy, PolicyGuideline
│   │   │   ├── submission.py   # ContentSubmission, ContentRevision
│   │   │   ├── verification.py # VerificationFinding, EvidenceReference
│   │   │   ├── review.py       # ReviewDecision
│   │   │   └── audit.py        # AuditEvent (immutable append-only)
│   │   └── schemas/            # Pydantic v2 DTOs and API contract schemas
│   │       ├── common.py       # Error envelopes and info responses
│   │       └── health.py       # Health check response schemas
│   ├── services/               # Foundational application services
│   │   └── audit_service.py    # Append-only audit logger with privacy hashing
│   └── main.py                 # Application factory & lifespan lifecycle
├── tests/                      # Automated test suite (23 focused tests)
├── .env.example                # Safe environment configuration template
├── .gitignore                  # Comprehensive secrets & artifacts exclusions
├── alembic.ini                 # Database migration tool configuration
└── pyproject.toml              # Project dependencies, tooling & test settings
```

---

## Core Domain Boundaries

Phase 1 formalizes the minimum foundational data structures across six domain pillars:

1. **Brand Workspace & Membership** (`app/domain/models/workspace.py`)
   - `BrandWorkspace`: Tenancy boundary representing an organization governing brand profiles.
   - `WorkspaceMember`: Associates users with explicit RBAC roles (`OWNER`, `ADMIN`, `REVIEWER`, `CONTRIBUTOR`, `VIEWER`).

2. **Versioned Brand Policies & Approved Guidelines** (`app/domain/models/policy.py`)
   - `BrandPolicy`: Explicitly versioned rule sets (`DRAFT`, `ACTIVE`, `DEPRECATED`, `ARCHIVED`).
   - `PolicyGuideline`: Granular verifiable clauses categorized by type (`BRAND_VOICE`, `TONE_CONSISTENCY`, `REGULATORY_COMPLIANCE`, `TERMINOLOGY`, `FACTUAL_ACCURACY`, `RESTRICTED_CLAIMS`), containing approved/prohibited examples and default severity.

3. **Content Submissions & Revisions** (`app/domain/models/submission.py`)
   - `ContentSubmission`: Tracks the workflow lifecycle (`DRAFT`, `SUBMITTED`, `IN_REVIEW`, `CHANGES_REQUESTED`, `APPROVED`, `REJECTED`).
   - `ContentRevision`: Sequential, immutable content snapshots submitted for verification.

4. **Verification Findings & Evidence References** (`app/domain/models/verification.py`)
   - `VerificationFinding`: Concrete flagged violations with exact character ranges and remediation advice.
   - `EvidenceReference`: Authoritative citations (`POLICY_CLAUSE`, `REGULATORY_STANDARD`, `APPROVED_LEXICON`, `CITATION`) backing every finding with confidence scores.

5. **Review & Approval Decisions** (`app/domain/models/review.py`)
   - `ReviewDecision`: Human governance verdicts (`APPROVE`, `REJECT`, `REQUEST_CHANGES`) with audit rationale and feedback notes.

6. **Append-Only Audit Events** (`app/domain/models/audit.py`)
   - `AuditEvent`: Append-only event log protected at the ORM layer against updates and deletes (omits `updated_at`). Stores structured event payloads with privacy-preserving SHA-256 client IP pseudonymization. (Note: True cryptographic tamper-evidence and hardware WORM storage are deferred to future security hardening phases).

---

## Prerequisites

- **Python**: Version 3.11 or higher (Tested with Python 3.13)
- **Database**:
  - Local development: SQLite Async (`sqlite+aiosqlite:///./inkloom_sentinel.db`)
  - Staging/Production: PostgreSQL 14+ (`postgresql+asyncpg://...`)

---

## Getting Started

### 1. Environment Configuration

Copy the example template into a local `.env` file:

```bash
# On Windows (PowerShell)
Copy-Item .env.example .env

# On Linux / macOS
cp .env.example .env
```

Review `.env` and adjust database credentials or log levels as needed. Production deployments require setting `ENVIRONMENT=production` and specifying a cryptographically strong `SECRET_KEY` (minimum 32 characters) along with a PostgreSQL `DATABASE_URL`.

### 2. Database Migrations

Apply the initial database schema to create all foundational tables:

```bash
# Run migrations up to latest version
python -m alembic upgrade head

# Rollback to base (if needed)
python -m alembic downgrade base
```

### 3. Starting the Local Development Server

Run the API using `uvicorn`:

```bash
# Start server with auto-reload enabled
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running:
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## API Endpoints Reference

### Health & Diagnostics Probes

| Method | Path | Description |
|---|---|---|
| `GET` | `/health/live` | Non-blocking process liveness probe (200 OK) |
| `GET` | `/health/ready` | Database readiness probe (200 OK if DB responsive, 503 if unavailable) |
| `GET` | `/health` | Comprehensive operational status, version, uptime, and backing service health |
| `GET` | `/api/v1/health/*` | Aliased versioned health probes |

### Platform Information

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/info` | Public metadata describing API version, environment tier, and routes |

---

## Automated Testing & Quality Checks

Run the automated test suite covering configuration, domain models, error handling, migrations, and health endpoints:

```bash
# Run all tests with pytest
python -m pytest -v

# Run with coverage report
python -m pytest --cov=app tests/

# Run code linting with Ruff
python -m ruff check .
```

---

## Security Foundation

- **Secrets Isolation**: Secrets are strictly read from environment variables; `.gitignore` prevents `.env`, `*.db`, keys, or credentials from being committed.
- **Production Guardrails**: The configuration validator rejects `DEBUG=True`, default placeholder `SECRET_KEY` values, or SQLite databases when `ENVIRONMENT=production`.
- **Sensitive Data Redaction**: The structured logging processor automatically redacts credentials, bearer tokens, passwords, and truncates large raw content payloads.
- **Privacy-Preserving Audit**: IP addresses are hashed using SHA-256 before being recorded in the audit trail.
- **Request Tracing**: All requests receive or preserve a unique `X-Request-ID` and report latency in `X-Process-Time`.

---

## Phase 1 Scope Boundaries & Next Phase

### Intentionally Excluded from Phase 1
- **No Frontend**: Landing page, dashboard, and visual components are deferred.
- **No Premature AI Engine**: Fake AI verification results and mock embeddings are excluded.
- **No Unnecessary Infrastructure**: Message brokers, Redis queues, and vector databases were omitted until required.

### Recommended Next Step: Phase 2
- **Phase 2 Objective**: Brand Policy Management & Rule Ingestion Engine.
  - Implement workspace-scoped policy authoring CRUD APIs (`/api/v1/workspaces/{id}/policies`).
  - Add guideline validation schemas, rule categories, and structured import/export (JSON/YAML).
  - Implement policy activation/deprecation state transitions with full audit trail logging.
