"""Inkloom Sentinel - Platform Information Endpoint."""

from fastapi import APIRouter

from app.core.config import settings
from app.domain.schemas.common import InfoResponse

router = APIRouter(tags=["Platform Information"])


@router.get(
    "/info",
    response_model=InfoResponse,
    summary="Platform Information",
    description="Returns public API version, environment tier, and configured endpoints.",
)
async def platform_info() -> InfoResponse:
    docs_url = "/docs" if not settings.is_production else None
    return InfoResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT.value,
        api_v1_prefix=settings.API_V1_PREFIX,
        docs_url=docs_url,
    )
