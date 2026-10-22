"""Inkloom Sentinel - Error Handling & Unified Exception Formats.

Standardized exception definitions and FastAPI error handlers.
All error responses conform to a consistent JSON envelope:
{
    "error": {
        "code": "...",
        "message": "...",
        "details": null | list | dict,
        "request_id": "..."
    }
}
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Any | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} '{identifier}' was not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: Any | None = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: Any | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class RateLimitExceededError(AppError):
    """Raised when an actor or IP exceeds rate limits."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        retry_after: int = 60,
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": retry_after},
        )
        self.retry_after = retry_after


class PayloadTooLargeError(AppError):
    """Raised when an HTTP request payload exceeds the maximum permitted byte size."""

    def __init__(self, max_bytes: int):
        super().__init__(
            message=f"Request payload exceeds maximum allowed size of {max_bytes} bytes.",
            code="PAYLOAD_TOO_LARGE",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details={"max_allowed_bytes": max_bytes},
        )


def build_error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str | None = None,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Format an error payload into the uniform API error structure."""
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform exception handlers on the FastAPI application instance."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "handled_app_error",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
        )
        resp_headers = {}
        if hasattr(exc, "retry_after"):
            resp_headers["Retry-After"] = str(exc.retry_after)
        return build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
            details=exc.details,
            headers=resp_headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        # Extract clean errors
        cleaned_details = []
        for error in exc.errors():
            loc = " -> ".join(str(part) for part in error.get("loc", []))
            cleaned_details.append(
                {
                    "location": loc,
                    "message": error.get("msg"),
                    "type": error.get("type"),
                }
            )
        logger.info(
            "request_validation_failed",
            error_count=len(cleaned_details),
            request_id=request_id,
        )
        return build_error_response(
            code="REQUEST_VALIDATION_ERROR",
            message="Request input validation failed.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            request_id=request_id,
            details=cleaned_details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        code_map = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            403: "FORBIDDEN",
            401: "UNAUTHORIZED",
            400: "BAD_REQUEST",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return build_error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_system_error",
            error=str(exc),
            error_type=exc.__class__.__name__,
            request_id=request_id,
            exc_info=True,
        )
        # In non-production, we do not leak full trace in response; standard safe error
        return build_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please contact support with the request ID.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=request_id,
        )
