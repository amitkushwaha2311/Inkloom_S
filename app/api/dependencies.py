"""Inkloom Sentinel - API Dependencies.

Reusable FastAPI dependency providers for database sessions,
request tracing, and service injection.
"""


from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.audit_service import AuditService


def get_request_id(request: Request) -> str | None:
    """Retrieve the unique correlation request ID attached to the request state."""
    return getattr(request.state, "request_id", None)


def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    """Dependency provider for AuditService with active transactional database session."""
    return AuditService(session=session)
