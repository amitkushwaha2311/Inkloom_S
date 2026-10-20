"""Tests for error handling, request ID tracing, and response middleware."""

import pytest
from httpx import AsyncClient

from app.core.errors import ConflictError, NotFoundError, ValidationError


@pytest.mark.asyncio
async def test_404_not_found_standardized_format(client: AsyncClient):
    """Verify missing endpoints return structured RFC 7807 compatible error envelope."""
    response = await client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]
    assert response.headers.get("X-Request-ID") == data["error"]["request_id"]


@pytest.mark.asyncio
async def test_request_id_and_process_time_headers(client: AsyncClient):
    """Verify every response includes X-Request-ID and X-Process-Time headers."""
    # Test with custom client request ID
    custom_id = "test-request-id-12345"
    response = await client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
    assert "X-Process-Time" in response.headers
    assert response.headers["X-Process-Time"].endswith("ms")

    # Test with auto-generated request ID
    response_auto = await client.get("/health/live")
    assert response_auto.status_code == 200
    assert response_auto.headers.get("X-Request-ID") is not None


def test_custom_app_exceptions():
    """Verify custom error classes initialize with appropriate HTTP status codes."""
    err_not_found = NotFoundError(resource="BrandPolicy", identifier="uuid-123")
    assert err_not_found.status_code == 404
    assert err_not_found.code == "NOT_FOUND"
    assert "uuid-123" in err_not_found.message

    err_conflict = ConflictError(message="Workspace slug already exists")
    assert err_conflict.status_code == 409
    assert err_conflict.code == "CONFLICT"

    err_validation = ValidationError(message="Policy clause cannot be empty")
    assert err_validation.status_code == 422
    assert err_validation.code == "VALIDATION_ERROR"
