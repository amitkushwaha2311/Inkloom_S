"""Inkloom Sentinel - Health & Diagnostics Schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = Field("ok", description="Process liveness state ('ok')")
    timestamp: datetime = Field(..., description="Timestamp of the health check in UTC")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Overall readiness state ('ready' or 'unhealthy')")
    database: dict[str, Any] = Field(..., description="Database connection health summary")
    timestamp: datetime = Field(..., description="Timestamp of the readiness evaluation")


class DetailedHealthResponse(BaseModel):
    status: str = Field(..., description="Overall health state ('healthy' or 'degraded')")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Deployment environment tier")
    uptime_seconds: float = Field(..., description="Seconds since process startup")
    dependencies: dict[str, Any] = Field(..., description="Status of all backing services")
    timestamp: datetime = Field(..., description="UTC evaluation timestamp")
