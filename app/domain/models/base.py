"""Inkloom Sentinel - Declarative Base & Common Mixins.

SQLAlchemy 2.0 declarative base with UTC timestamping and UUID primary keys.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base class for all persistent domain entities."""

    pass


class UUIDPrimaryKeyMixin:
    """Provides a consistent UUID primary key across PostgreSQL and SQLite."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-10,
    )


class TimestampMixin:
    """Provides automatic UTC audit timestamps for entity creation and mutation."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
