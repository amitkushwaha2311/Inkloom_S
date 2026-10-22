"""Inkloom Sentinel - HTTP Middleware.

Request ID tracing, timing headers, and secure request logging.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.errors import PayloadTooLargeError, build_error_response
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns unique correlation IDs, enforces security headers, and measures request duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve or generate correlation request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        # Enforce maximum payload size limit
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_bytes = int(content_length)
                if length_bytes > settings.MAX_REQUEST_BODY_BYTES:
                    exc = PayloadTooLargeError(settings.MAX_REQUEST_BODY_BYTES)
                    response = build_error_response(
                        code=exc.code,
                        message=exc.message,
                        status_code=exc.status_code,
                        request_id=request_id,
                        details=exc.details,
                    )
                    response.headers["X-Request-ID"] = request_id
                    response.headers["X-Content-Type-Options"] = "nosniff"
                    response.headers["X-Frame-Options"] = "DENY"
                    return response
            except ValueError:
                pass

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response_time_ms = round(process_time * 1000, 2)

            # Traceability headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{response_time_ms}ms"

            # Security response headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if settings.is_production:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains; preload"
                )

            # Safe structured request logging (excludes authorization headers, bodies, etc.)
            logger.info(
                "http_request_finished",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=response_time_ms,
                request_id=request_id,
            )
            return response
        except Exception as exc:
            process_time = time.perf_counter() - start_time
            response_time_ms = round(process_time * 1000, 2)
            logger.error(
                "http_request_exception",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                duration_ms=response_time_ms,
                request_id=request_id,
            )
            raise exc
