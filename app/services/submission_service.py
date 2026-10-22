"""Inkloom Sentinel - Content Submission & Revision Service.

Handles content ingestion, metadata management, and immutable revision tracking
under strict workspace isolation and auditability.
"""

import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import AuditEventType, SubmissionStatus
from app.domain.models.submission import ContentRevision, ContentSubmission
from app.domain.schemas.submission import (
    ContentRevisionCreate,
    ContentRevisionResponse,
    ContentSubmissionCreate,
    ContentSubmissionDetailResponse,
    ContentSubmissionResponse,
    ContentSubmissionUpdate,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)


def serialize_revision(rev: ContentRevision) -> ContentRevisionResponse:
    """Transform a ContentRevision ORM instance into its Pydantic response."""
    payload = rev.metadata_payload or {}
    return ContentRevisionResponse(
        id=rev.id,
        submission_id=rev.submission_id,
        revision_number=rev.revision_number,
        content_text=rev.content_text,
        content_format=rev.content_format,
        content_type=payload.get("content_type"),
        content_hash=payload.get("content_hash"),
        created_by_id=payload.get("created_by_id"),
        change_summary=payload.get("change_summary"),
        source_metadata=payload.get("source_metadata"),
        submitted_at=rev.submitted_at,
        created_at=rev.created_at,
    )


def serialize_submission(sub: ContentSubmission) -> ContentSubmissionResponse:
    """Transform a ContentSubmission ORM instance into its summary response."""
    revisions = sub.revisions or []
    latest_rev_num = max((r.revision_number for r in revisions), default=1)
    return ContentSubmissionResponse(
        id=sub.id,
        workspace_id=sub.workspace_id,
        title=sub.title,
        campaign_tag=sub.campaign_tag,
        status=sub.status,
        author_id=sub.author_id,
        revision_count=len(revisions),
        latest_revision_number=latest_rev_num,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


def serialize_submission_detail(sub: ContentSubmission) -> ContentSubmissionDetailResponse:
    """Transform a ContentSubmission ORM instance into its detail response with revisions."""
    revisions = sorted(sub.revisions or [], key=lambda r: r.revision_number)
    serialized_revs = [serialize_revision(r) for r in revisions]
    latest_rev = serialized_revs[-1] if serialized_revs else None
    return ContentSubmissionDetailResponse(
        id=sub.id,
        workspace_id=sub.workspace_id,
        title=sub.title,
        campaign_tag=sub.campaign_tag,
        status=sub.status,
        author_id=sub.author_id,
        revision_count=len(serialized_revs),
        latest_revision=latest_rev,
        revisions=serialized_revs,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


class SubmissionService:
    """Service managing content submissions and immutable revision history."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------
    # Content submission creation & retrieval
    # ------------------------------------------------------------------

    async def create_submission(
        self,
        workspace_id: uuid.UUID,
        data: ContentSubmissionCreate,
        author_id: str,
    ) -> ContentSubmission:
        """Create a new submission along with its immutable v1 revision.

        Guarantees transactional atomicity: if revision creation fails,
        the entire submission is rolled back.
        """
        # Calculate SHA-256 integrity hash
        content_hash = hashlib.sha256(data.content_text.encode("utf-8")).hexdigest()

        # Build initial revision metadata
        initial_metadata = {
            "content_type": data.content_type.value,
            "content_hash": content_hash,
            "created_by_id": author_id,
            "source_metadata": data.source_metadata or {},
            "change_summary": "Initial submission",
        }

        submission = ContentSubmission(
            workspace_id=workspace_id,
            title=data.title,
            campaign_tag=data.campaign_tag,
            status=data.status,
            author_id=author_id,
        )
        self.session.add(submission)
        await self.session.flush()

        initial_revision = ContentRevision(
            submission_id=submission.id,
            revision_number=1,
            content_text=data.content_text,
            content_format=data.content_format,
            metadata_payload=initial_metadata,
        )
        self.session.add(initial_revision)
        await self.session.flush()

        # Audit recording — never logs full content text
        await self.audit.record_event(
            event_type=AuditEventType.CONTENT_SUBMITTED,
            actor_id=author_id,
            resource_type="ContentSubmission",
            resource_id=str(submission.id),
            workspace_id=workspace_id,
            event_payload={
                "title": submission.title,
                "campaign_tag": submission.campaign_tag,
                "status": submission.status.value,
                "revision_number": 1,
                "content_hash": content_hash,
                "content_type": data.content_type.value,
            },
        )

        logger.info(
            "content_submission_created",
            submission_id=str(submission.id),
            workspace_id=str(workspace_id),
            actor=author_id,
        )

        # Refresh with eager-loaded revisions
        await self.session.refresh(submission, ["revisions"])
        return submission

    async def list_submissions(
        self,
        workspace_id: uuid.UUID,
        status: SubmissionStatus | None = None,
        campaign_tag: str | None = None,
        author_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ContentSubmission], int]:
        """Return paginated submissions for a workspace with optional filtering."""
        query = (
            select(ContentSubmission)
            .where(ContentSubmission.workspace_id == workspace_id)
            .options(selectinload(ContentSubmission.revisions))
            .order_by(ContentSubmission.created_at.desc())
        )

        count_query = select(func.count(ContentSubmission.id)).where(
            ContentSubmission.workspace_id == workspace_id
        )

        if status is not None:
            query = query.where(ContentSubmission.status == status)
            count_query = count_query.where(ContentSubmission.status == status)

        if campaign_tag is not None:
            query = query.where(ContentSubmission.campaign_tag == campaign_tag)
            count_query = count_query.where(ContentSubmission.campaign_tag == campaign_tag)

        if author_id is not None:
            query = query.where(ContentSubmission.author_id == author_id)
            count_query = count_query.where(ContentSubmission.author_id == author_id)

        offset = (page - 1) * page_size
        paginated_query = query.offset(offset).limit(page_size)

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        items_result = await self.session.execute(paginated_query)
        items = list(items_result.scalars().all())

        return items, total

    async def get_submission_or_404(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ContentSubmission:
        """Retrieve submission verifying workspace isolation.

        Raises NotFoundError (404) if non-existent or cross-workspace.
        """
        query = (
            select(ContentSubmission)
            .where(
                ContentSubmission.id == submission_id,
                ContentSubmission.workspace_id == workspace_id,
            )
            .options(selectinload(ContentSubmission.revisions))
        )
        result = await self.session.execute(query)
        submission = result.scalar_one_or_none()
        if submission is None:
            raise NotFoundError("ContentSubmission", str(submission_id))
        return submission

    async def update_submission_metadata(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
        data: ContentSubmissionUpdate,
        actor_id: str,
    ) -> ContentSubmission:
        """Update mutable metadata (title, campaign_tag, status) on a submission.

        Note: Content text CANNOT be edited here — changes must create a new revision.
        """
        submission = await self.get_submission_or_404(submission_id, workspace_id)

        changes: dict[str, str | None] = {}

        if data.title is not None and data.title != submission.title:
            changes["title"] = data.title
            submission.title = data.title

        if data.campaign_tag is not None:
            cleaned_tag = data.campaign_tag.strip() or None
            if cleaned_tag != submission.campaign_tag:
                changes["campaign_tag"] = cleaned_tag
                submission.campaign_tag = cleaned_tag

        if data.status is not None and data.status != submission.status:
            # Validate status transition
            valid_statuses = {
                SubmissionStatus.DRAFT,
                SubmissionStatus.SUBMITTED,
                SubmissionStatus.IN_REVIEW,
                SubmissionStatus.CHANGES_REQUESTED,
                SubmissionStatus.APPROVED,
                SubmissionStatus.REJECTED,
            }
            if data.status not in valid_statuses:
                raise ValidationError(f"Invalid status '{data.status.value}'.")
            changes["status"] = data.status.value
            submission.status = data.status

        if not changes:
            return submission

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CONTENT_METADATA_UPDATED,
            actor_id=actor_id,
            resource_type="ContentSubmission",
            resource_id=str(submission.id),
            workspace_id=workspace_id,
            event_payload=changes,
        )

        return submission

    # ------------------------------------------------------------------
    # Revision management
    # ------------------------------------------------------------------

    async def create_revision(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
        data: ContentRevisionCreate,
        actor_id: str,
    ) -> ContentRevision:
        """Append a new immutable revision with optimistic concurrency protection."""
        submission = await self.get_submission_or_404(submission_id, workspace_id)

        # Determine current latest revision number
        existing_revs = submission.revisions or []
        current_latest_num = max((r.revision_number for r in existing_revs), default=0)

        # Concurrency guard: reject if expected_revision_number doesn't match
        if (
            data.expected_revision_number is not None
            and data.expected_revision_number != current_latest_num
        ):
            raise ConflictError(
                f"Concurrency conflict: expected revision {data.expected_revision_number}, "
                f"but current revision is {current_latest_num}. Please refresh before updating."
            )

        new_rev_num = current_latest_num + 1
        content_hash = hashlib.sha256(data.content_text.encode("utf-8")).hexdigest()

        # Inherit content_type from previous revision if not specified
        prev_type = "marketing_copy"
        if existing_revs:
            latest_rev = max(existing_revs, key=lambda r: r.revision_number)
            prev_type = (latest_rev.metadata_payload or {}).get("content_type", "marketing_copy")
        content_type = data.content_type.value if data.content_type else prev_type

        metadata_payload = {
            "content_type": content_type,
            "content_hash": content_hash,
            "created_by_id": actor_id,
            "source_metadata": data.source_metadata or {},
            "change_summary": data.change_summary or "",
        }

        revision = ContentRevision(
            submission_id=submission.id,
            revision_number=new_rev_num,
            content_text=data.content_text,
            content_format=data.content_format,
            metadata_payload=metadata_payload,
        )
        self.session.add(revision)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.CONTENT_REVISED,
            actor_id=actor_id,
            resource_type="ContentRevision",
            resource_id=str(revision.id),
            workspace_id=workspace_id,
            event_payload={
                "submission_id": str(submission.id),
                "revision_number": revision.revision_number,
                "content_hash": content_hash,
                "change_summary": data.change_summary,
            },
        )

        logger.info(
            "content_revision_created",
            submission_id=str(submission.id),
            revision_number=new_rev_num,
            actor=actor_id,
        )

        return revision

    async def get_revision_or_404(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
        revision_number: int,
    ) -> ContentRevision:
        """Retrieve a specific revision of a submission, verifying workspace boundary."""
        # Ensure submission belongs to workspace
        await self.get_submission_or_404(submission_id, workspace_id)

        query = select(ContentRevision).where(
            ContentRevision.submission_id == submission_id,
            ContentRevision.revision_number == revision_number,
        )
        result = await self.session.execute(query)
        rev = result.scalar_one_or_none()
        if rev is None:
            raise NotFoundError("ContentRevision", f"{submission_id}/r/{revision_number}")
        return rev

    async def list_revisions(
        self,
        submission_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[ContentRevision]:
        """List all revisions for a submission in chronological order."""
        await self.get_submission_or_404(submission_id, workspace_id)

        query = (
            select(ContentRevision)
            .where(ContentRevision.submission_id == submission_id)
            .order_by(ContentRevision.revision_number.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
