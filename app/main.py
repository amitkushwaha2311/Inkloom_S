"""Inkloom Sentinel - Application Entrypoint & Factory.

Assembles FastAPI application, registers middleware, configures lifespan lifecycle,
and binds API routes and global error handlers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.v1.endpoints.health import router as root_health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import check_database_health, close_db_engine
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown sequences."""
    # Startup sequence
    setup_logging()
    logger.info(
        "inkloom_sentinel_starting",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT.value,
        debug=settings.DEBUG,
    )

    # Initial non-blocking connectivity check
    db_status = await check_database_health()
    if db_status.get("healthy"):
        logger.info("database_connectivity_verified", dialect=db_status.get("dialect"))
    else:
        logger.warning("database_initial_connectivity_unhealthy", details=db_status)

    yield

    # Shutdown sequence
    logger.info("inkloom_sentinel_shutting_down")
    await close_db_engine()
    logger.info("inkloom_sentinel_stopped")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    # Restrict interactive docs in production environments
    docs_url = "/docs" if not settings.is_production else None
    redoc_url = "/redoc" if not settings.is_production else None
    openapi_url = "/openapi.json" if not settings.is_production else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Evidence-backed AI brand-governance platform for verifying content "
            "against versioned brand guidelines and regulatory policies before publication."
        ),
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Register Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register custom request context and tracing middleware
    app.add_middleware(RequestContextMiddleware)

    # Register standardized exception handlers
    register_exception_handlers(app)

    # Include root health router for direct container probe compatibility
    app.include_router(root_health_router)

    # Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
