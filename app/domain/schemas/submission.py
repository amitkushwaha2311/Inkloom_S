"""Inkloom Sentinel - Content Submission & Revision Schemas.

Pydantic schemas governing content drafting, submission, and immutable revision tracking.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import ContentType, SubmissionStatus

_ALLOWED_FORMATS = {"markdown", "plain_text", "html", "text"}
_MAX_CONTENT_LENGTH = 100_000  # 100 KB text limit to protect against unbounded payload DoS


class ContentRevisionCreate(BaseModel):
    """Payload to create a new immutable revision of an existing content submission."""

    content_text: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_CONTENT_LENGTH,
        description="The updated text content.",
    )
    content_format: str = Field(
        default="markdown",
        max_length=32,
        description="Format: markdown, plain_text, or html.",
    )
    content_type: ContentType | None = Field(
        default=None,
        description="Optional updated asset classification.",
    )
    source_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional context (e.g. channel, platform, campaign details).",
    )
    change_summary: str | None = Field(
        default=None,
        max_length=500,
        description="Brief note describing what changed in this revision.",
    )
    expected_revision_number: int | None = Field(
        default=None,
        description=(
            "Optimistic concurrency control: if provided, the revision will only be created "
            "if the current latest revision number matches this value. Prevents lost updates."
        ),
    )

    @field_validator("content_text")
    @classmethod
    def validate_content_text_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Content text cannot be empty or whitespace only.")
        return v

    @field_validator("content_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        fmt = v.lower().strip()
        if fmt not in _ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported content_format '{v}'. Allowed: {sorted(_ALLOWED_FORMATS)}"
            )
        return fmt


class ContentSubmissionCreate(BaseModel):
    """Payload to create a new content submission with its initial (v1) revision."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Descriptive title of the content draft.",
    )
    campaign_tag: str | None = Field(
        default=None,
        max_length=100,
        description="Optional tag for grouping related campaign assets.",
    )
    content_text: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_CONTENT_LENGTH,
        description="The initial text content.",
    )
    content_type: ContentType = Field(
        default=ContentType.MARKETING_COPY,
        description="Asset type classification.",
    )
    content_format: str = Field(
        default="markdown",
        max_length=32,
        description="Format: markdown, plain_text, or html.",
    )
    source_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Origin metadata (e.g. source channel, author notes).",
    )
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT,
        description="Initial lifecycle status (DRAFT or SUBMITTED).",
    )

    @field_validator("title")
    @classmethod
    def validate_title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace only.")
        return stripped

    @field_validator("content_text")
    @classmethod
    def validate_content_text_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Content text cannot be empty or whitespace only.")
        return v

    @field_validator("content_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        fmt = v.lower().strip()
        if fmt not in _ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported content_format '{v}'. Allowed: {sorted(_ALLOWED_FORMATS)}"
            )
        return fmt

    @field_validator("status")
    @classmethod
    def validate_initial_status(cls, v: SubmissionStatus) -> SubmissionStatus:
        if v not in (SubmissionStatus.DRAFT, SubmissionStatus.SUBMITTED):
            raise ValueError("Initial submission status must be either DRAFT or SUBMITTED.")
        return v


class ContentSubmissionUpdate(BaseModel):
    """Update metadata for an existing content submission.

    Note: Content text CANNOT be modified through this schema; content edits must
    use the POST /submissions/{id}/revisions endpoint to preserve revision integrity.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New title for the submission.",
    )
    campaign_tag: str | None = Field(
        default=None,
        max_length=100,
        description="New campaign tag (pass empty string or null to clear).",
    )
    status: SubmissionStatus | None = Field(
        default=None,
        description="New lifecycle status.",
    )

    @field_validator("title")
    @classmethod
    def validate_title_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Title cannot be whitespace only.")
            return stripped
        return v


class ContentRevisionResponse(BaseModel):
    """Serialized representation of an immutable content revision."""

    id: uuid.UUID
    submission_id: uuid.UUID
    revision_number: int
    content_text: str
    content_format: str
    content_type: str | None = None
    content_hash: str | None = None
    created_by_id: str | None = None
    change_summary: str | None = None
    source_metadata: dict[str, Any] | None = None
    submitted_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentSubmissionResponse(BaseModel):
    """Summary representation of a content submission."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    campaign_tag: str | None = None
    status: SubmissionStatus
    author_id: str
    revision_count: int = 1
    latest_revision_number: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentSubmissionDetailResponse(BaseModel):
    """Detailed representation of a content submission with full revision history."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    campaign_tag: str | None = None
    status: SubmissionStatus
    author_id: str
    revision_count: int
    latest_revision: ContentRevisionResponse | None = None
    revisions: list[ContentRevisionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentSubmissionListResponse(BaseModel):
    """Paginated list of content submissions."""

    items: list[ContentSubmissionResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
