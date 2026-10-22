"""Inkloom Sentinel - Common Data Transfer Schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable summary of the error")
    details: Any | None = Field(None, description="Optional granular diagnostic details")
    request_id: str | None = Field(
        None, description="Unique correlation ID for tracing the request"
    )


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class InfoResponse(BaseModel):
    app_name: str
    version: str
    environment: str
    api_v1_prefix: str
    docs_url: str | None = None
