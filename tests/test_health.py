"""Tests for health check and diagnostics endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_endpoint(client: AsyncClient):
    """Verify liveness probe returns 200 OK with timestamp."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data

    # Test namespaced alias /api/v1/health/live
    v1_response = await client.get("/api/v1/health/live")
    assert v1_response.status_code == 200
    assert v1_response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_endpoint_healthy(client: AsyncClient):
    """Verify readiness probe reports ready when database responds."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["healthy"] is True
    assert "latency_ms" in data["database"]
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_endpoint_unhealthy(client: AsyncClient):
    """Verify readiness probe returns 503 when database connectivity fails."""
    with patch(
        "app.api.v1.endpoints.health.check_database_health",
        return_value={"healthy": False, "latency_ms": 150.0, "error": "Connection timed out"},
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"]["healthy"] is False


@pytest.mark.asyncio
async def test_detailed_health_endpoint(client: AsyncClient):
    """Verify detailed health endpoint reports environment, version, uptime, and backing services."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
    assert "uptime_seconds" in data
    assert "database" in data["dependencies"]
    assert data["dependencies"]["database"]["healthy"] is True


@pytest.mark.asyncio
async def test_platform_info_endpoint(client: AsyncClient):
    """Verify platform metadata info endpoint returns app metadata."""
    response = await client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Inkloom Sentinel API"
    assert data["api_v1_prefix"] == "/api/v1"
    assert "version" in data
    assert "environment" in data
