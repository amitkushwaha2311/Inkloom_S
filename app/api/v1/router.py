"""Inkloom Sentinel - API v1 Master Router."""

from fastapi import APIRouter

from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.evidence import (
    claims_router,
    sources_router,
)
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.info import router as info_router
from app.api.v1.endpoints.policies import router as policies_router
from app.api.v1.endpoints.reviews import router as reviews_router
from app.api.v1.endpoints.semantic import router as semantic_router
from app.api.v1.endpoints.submissions import router as submissions_router
from app.api.v1.endpoints.verification import router as verification_router
from app.api.v1.endpoints.workspaces import router as workspaces_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(info_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(policies_router)
api_v1_router.include_router(submissions_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(claims_router)
api_v1_router.include_router(semantic_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(audit_router)
