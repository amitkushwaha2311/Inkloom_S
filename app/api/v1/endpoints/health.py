"""Inkloom Sentinel - Health & Diagnostics Endpoints.

Provides decoupled liveness and readiness probes along with detailed status reports
without leaking sensitive internal infrastructure details.
"""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.database import check_database_health
from app.domain.schemas.health import (
    DetailedHealthResponse,
    LivenessResponse,
    ReadinessResponse,
)

router = APIRouter(prefix="/health", tags=["Diagnostics & Health"])

# Process start time for uptime tracking
START_TIME = time.time()


@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Liveness Probe",
    description="Fast non-blocking probe verifying the process is running and accepting HTTP requests.",
)
async def liveness_probe() -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service is ready to handle traffic"},
        503: {"description": "Service or required dependencies are degraded"},
    },
    summary="Application Readiness Probe",
    description="Verifies downstream database connectivity before routing user traffic.",
)
async def readiness_probe(response: Response) -> ReadinessResponse:
    db_health = await check_database_health()
    is_ready = db_health.get("healthy", False)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unhealthy"
    else:
        overall_status = "ready"

    return ReadinessResponse(
        status=overall_status,
        database=db_health,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "",
    response_model=DetailedHealthResponse,
    responses={
        200: {"description": "All subsystems are healthy"},
        503: {"description": "One or more subsystems are degraded"},
    },
    summary="Comprehensive Health Summary",
    description="Detailed operational status including version, environment, uptime, and backing services.",
)
async def detailed_health(response: Response) -> DetailedHealthResponse:
    db_health = await check_database_health()
    is_healthy = db_health.get("healthy", False)

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    uptime = round(time.time() - START_TIME, 2)

    return DetailedHealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT.value,
        uptime_seconds=uptime,
        dependencies={
            "database": db_health,
        },
        timestamp=datetime.now(UTC),
    )
