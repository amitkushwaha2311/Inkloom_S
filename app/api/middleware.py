"""Inkloom Sentinel - HTTP Middleware.

Request ID tracing, timing headers, and secure request logging.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns unique correlation IDs, measures processing duration, and safely logs HTTP events."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve or generate correlation request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response_time_ms = round(process_time * 1000, 2)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{response_time_ms}ms"

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
