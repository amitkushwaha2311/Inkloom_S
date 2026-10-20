"""Inkloom Sentinel - API v1 Master Router.

Aggregates all version 1 API endpoints under a unified namespace.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.info import router as info_router

api_v1_router = APIRouter()

# Mount health & diagnostic probes
api_v1_router.include_router(health_router)

# Mount platform info
api_v1_router.include_router(info_router)
