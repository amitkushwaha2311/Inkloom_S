"""Inkloom Sentinel - Structured Logging Configuration.

Provides structured logging without leaking sensitive credentials,
authorization tokens, or full submitted content payloads.
"""

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings

# Sensitive keys that must be redacted from log context and event dictionaries
REDACTED_KEYS = {
    "password",
    "secret",
    "secret_key",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
}

MAX_CONTENT_LOG_LENGTH = 120  # Limit length of user content previews in logs


def redact_sensitive_data(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to scrub secrets, credentials, and truncate large payload excerpts."""
    cleaned = {}
    for key, value in event_dict.items():
        lower_key = str(key).lower()
        if any(secret_term in lower_key for secret_term in REDACTED_KEYS):
            cleaned[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 1000 and "content" in lower_key:
            cleaned[key] = f"{value[:MAX_CONTENT_LOG_LENGTH]}... [TRUNCATED {len(value)} chars]"
        elif isinstance(value, dict):
            # Recursively scrub nested dicts (up to 1 level for safety)
            sub_cleaned = {}
            for sub_k, sub_v in value.items():
                if any(secret_term in str(sub_k).lower() for secret_term in REDACTED_KEYS):
                    sub_cleaned[sub_k] = "[REDACTED]"
                else:
                    sub_cleaned[sub_k] = sub_v
            cleaned[key] = sub_cleaned
        else:
            cleaned[key] = value
    return cleaned


def setup_logging() -> None:
    """Initialize structured logging pipelines."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_sensitive_data,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_JSON_FORMAT or settings.is_production:
        formatter_processor = structlog.processors.JSONRenderer()
    else:
        formatter_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Standard library root logging configuration
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            formatter_processor,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str = "inkloom"):
    """Get a structured logger instance."""
    return structlog.get_logger(name)
