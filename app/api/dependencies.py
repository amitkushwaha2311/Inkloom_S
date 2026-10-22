"""Inkloom Sentinel - API Dependencies.

Centralized FastAPI dependency providers for:
- Database session injection
- Authentication: verified JWT → User object (replaces unauthenticated placeholder)
- Service injection: AuthService, PolicyService, WorkspaceService, AuditService
- Request metadata: request_id, client_ip, user_agent

Security contract:
    require_current_user() extracts the Bearer token from the Authorization header,
    decodes and validates the JWT signature and expiry, then loads the User from the
    database. The actor identity is NEVER taken from a client-controlled header.

    The old get_actor_id() placeholder that read X-Actor-ID has been removed.
    Any code that referenced it must be updated to use require_current_user().
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.errors import UnauthorizedError
from app.domain.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.claim_service import ClaimService
from app.services.policy_service import PolicyService
from app.services.review_service import ReviewService
from app.services.semantic_service import SemanticService
from app.services.submission_service import SubmissionService
from app.services.verification_service import VerificationService
from app.services.workspace_service import WorkspaceService

# HTTPBearer extracts the Authorization: Bearer <token> header.
# auto_error=False means we raise our own UnauthorizedError instead of FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request metadata
# ---------------------------------------------------------------------------


def get_request_id(request: Request) -> str | None:
    """Retrieve the unique correlation request ID attached to the request state."""
    return getattr(request.state, "request_id", None)


def get_client_ip(request: Request) -> str | None:
    """Extract the client IP address (respects X-Forwarded-For if set by a trusted proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    return AuditService(session=session)


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> AuthService:
    return AuthService(
        session=session,
        audit=audit,
        secret_key=settings.SECRET_KEY,
        access_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def get_policy_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> PolicyService:
    return PolicyService(session=session, audit=audit)


def get_workspace_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> WorkspaceService:
    return WorkspaceService(session=session, audit=audit)


def get_submission_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> SubmissionService:
    return SubmissionService(session=session, audit=audit)


def get_verification_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> VerificationService:
    return VerificationService(session=session, audit=audit)


def get_claim_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> ClaimService:
    return ClaimService(session=session, audit=audit)


def get_semantic_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> SemanticService:
    return SemanticService(session=session, audit=audit)


def get_review_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
    submission_service: SubmissionService = Depends(get_submission_service),
) -> ReviewService:
    return ReviewService(session=session, audit=audit, submission_service=submission_service)


def get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    return AnalyticsService(session=session)


# ---------------------------------------------------------------------------
# Authentication dependency — the single source of verified actor identity
# ---------------------------------------------------------------------------


async def require_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    auth_svc: AuthService = Depends(get_auth_service),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Verify a Bearer JWT and return the authenticated User.

    Raises UnauthorizedError (401) if:
    - No Authorization header is present
    - The token is malformed, has an invalid signature, or has expired
    - The token type claim is wrong
    - The user referenced by the token no longer exists or is inactive

    This dependency is the ONLY way to establish actor identity.
    Never accept X-Actor-ID or any other client-controlled header as identity.
    """
    if credentials is None:
        raise UnauthorizedError("Authentication required. Provide a Bearer token.")

    payload = auth_svc.verify_access_token(credentials.credentials)

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Access token is missing subject claim.")

    try:
        import uuid as _uuid

        user_uuid = _uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError("Access token contains an invalid subject claim.") from None

    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("User account not found.")
    if not user.is_active:
        raise UnauthorizedError("User account is disabled.")

    return user


# Convenience type alias for endpoint signatures
CurrentUser = Annotated[User, Depends(require_current_user)]
