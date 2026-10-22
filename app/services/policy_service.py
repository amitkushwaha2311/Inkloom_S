"""Inkloom Sentinel - Brand Policy Service.

Business logic for brand policy lifecycle management, guideline ingestion,
and version control. All mutation operations record audit events.

Authorization notice:
    Authentication and workspace membership enforcement are NOT yet implemented
    (deferred to Phase 3). All write endpoints are currently unguarded against
    unauthenticated callers. Callers must pass an explicit actor_id string; the
    system trusts it as-is and will not invent or forge actor identities.
    This limitation is documented and must be addressed before production deployment.

Lifecycle transition table:
    DRAFT  → ACTIVE      (activate: requires ≥1 guideline)
    DRAFT  → ARCHIVED    (archive: soft close without activation)
    ACTIVE → DEPRECATED  (deprecate: must supply a reason)
    ACTIVE → ARCHIVED    (archive: emergency close)
    DEPRECATED → ARCHIVED

Invalid transitions raise ValidationError with a clear message.

SQLAlchemy async note:
    We never use session.get() for entities with lazy/selectin relationships
    because that triggers implicit IO outside the async greenlet.
    All loads use explicit select() statements with joinedload/selectinload
    options so SQLAlchemy can schedule them correctly.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import AuditEventType, PolicyStatus
from app.domain.models.policy import BrandPolicy, PolicyGuideline
from app.domain.models.workspace import BrandWorkspace
from app.domain.schemas.policy import (
    GuidelineCreate,
    GuidelineUpdate,
    PolicyCreate,
    PolicyUpdate,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# Valid status transitions: maps current status → allowed next statuses
_VALID_TRANSITIONS: dict[PolicyStatus, set[PolicyStatus]] = {
    PolicyStatus.DRAFT: {PolicyStatus.ACTIVE, PolicyStatus.ARCHIVED},
    PolicyStatus.ACTIVE: {PolicyStatus.DEPRECATED, PolicyStatus.ARCHIVED},
    PolicyStatus.DEPRECATED: {PolicyStatus.ARCHIVED},
    PolicyStatus.ARCHIVED: set(),  # Terminal state — no further transitions
}


class PolicyService:
    """Manages brand policy lifecycle, versioning, and guideline ingestion."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------
    # Workspace helpers
    # ------------------------------------------------------------------

    async def _require_workspace(self, workspace_id: uuid.UUID) -> BrandWorkspace:
        """Load a workspace or raise NotFoundError.

        Uses an explicit select() rather than session.get() to avoid triggering
        implicit selectin relationship loading outside the async greenlet.
        """
        result = await self.session.execute(
            select(BrandWorkspace).where(BrandWorkspace.id == workspace_id)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            raise NotFoundError("BrandWorkspace", str(workspace_id))
        return ws

    # ------------------------------------------------------------------
    # Policy helpers
    # ------------------------------------------------------------------

    async def _require_policy(self, workspace_id: uuid.UUID, policy_id: uuid.UUID) -> BrandPolicy:
        """Load a policy with guidelines eagerly, enforcing workspace ownership."""
        result = await self.session.execute(
            select(BrandPolicy)
            .where(
                BrandPolicy.id == policy_id,
                BrandPolicy.workspace_id == workspace_id,
            )
            .options(selectinload(BrandPolicy.guidelines))
        )
        policy = result.scalar_one_or_none()
        # Return 404 for both "not found" and "wrong workspace" to avoid information leakage
        if policy is None:
            raise NotFoundError("BrandPolicy", str(policy_id))
        return policy

    async def _require_guideline(
        self, policy_id: uuid.UUID, guideline_id: uuid.UUID
    ) -> PolicyGuideline:
        """Load a guideline, enforcing that it belongs to the specified policy."""
        result = await self.session.execute(
            select(PolicyGuideline).where(
                PolicyGuideline.id == guideline_id,
                PolicyGuideline.policy_id == policy_id,
            )
        )
        guideline = result.scalar_one_or_none()
        if guideline is None:
            raise NotFoundError("PolicyGuideline", str(guideline_id))
        return guideline

    def _require_draft(self, policy: BrandPolicy) -> None:
        """Raise ValidationError unless the policy is in DRAFT status."""
        if policy.status != PolicyStatus.DRAFT:
            raise ValidationError(
                f"This operation requires policy status DRAFT, but current status is '{policy.status.value}'. "
                "Create a new version to modify an active or deprecated policy."
            )

    @staticmethod
    def _apply_transition(policy: BrandPolicy, target: PolicyStatus) -> None:
        """Validate and apply a lifecycle status transition."""
        allowed = _VALID_TRANSITIONS.get(policy.status, set())
        if target not in allowed:
            allowed_str = (
                ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
                if allowed
                else "none (terminal state)"
            )
            raise ValidationError(
                f"Cannot transition policy from '{policy.status.value}' to '{target.value}'. "
                f"Allowed transitions from '{policy.status.value}': {allowed_str}."
            )
        policy.status = target

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    async def create_policy(
        self,
        workspace_id: uuid.UUID,
        data: PolicyCreate,
        actor_id: str,
    ) -> BrandPolicy:
        """Create a new DRAFT policy at version 1 within a workspace."""
        await self._require_workspace(workspace_id)

        policy = BrandPolicy(
            workspace_id=workspace_id,
            name=data.name,
            description=data.description,
            version=1,
            status=PolicyStatus.DRAFT,
            created_by_id=actor_id,
        )
        self.session.add(policy)

        try:
            await self.session.flush()
        except IntegrityError as err:
            await self.session.rollback()
            raise ConflictError(
                f"A policy named '{data.name}' at version 1 already exists in this workspace."
            ) from err

        # Ingest any inline guidelines
        for g_data in data.guidelines:
            await self._add_guideline_to_policy(policy, g_data, actor_id, flush=False)

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_CREATED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(policy.id),
            workspace_id=workspace_id,
            event_payload={
                "name": policy.name,
                "version": policy.version,
                "guideline_count": len(data.guidelines),
            },
        )
        logger.info("policy_created", policy_id=str(policy.id), name=policy.name, actor=actor_id)

        # Reload with guidelines eager-loaded so callers get the full object
        return await self._require_policy(workspace_id, policy.id)

    async def list_policies(
        self,
        workspace_id: uuid.UUID,
        *,
        status: PolicyStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BrandPolicy], int]:
        """Return a paginated list of policies in a workspace, with optional status filter."""
        await self._require_workspace(workspace_id)

        # Count query — use a separate simple select for correctness
        count_filters = [BrandPolicy.workspace_id == workspace_id]
        if status is not None:
            count_filters.append(BrandPolicy.status == status)

        total_result = await self.session.execute(
            select(func.count(BrandPolicy.id)).where(*count_filters)
        )
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        items_result = await self.session.execute(
            select(BrandPolicy)
            .where(*count_filters)
            .options(selectinload(BrandPolicy.guidelines))
            .order_by(BrandPolicy.name, BrandPolicy.version.desc())
            .limit(page_size)
            .offset(offset)
        )
        items = list(items_result.scalars().all())
        return items, total

    async def get_policy(self, workspace_id: uuid.UUID, policy_id: uuid.UUID) -> BrandPolicy:
        """Retrieve a specific policy with all its guidelines."""
        return await self._require_policy(workspace_id, policy_id)

    async def get_version_history(
        self, workspace_id: uuid.UUID, policy_name: str
    ) -> list[BrandPolicy]:
        """Return all versions of policies with the given name in ascending version order."""
        await self._require_workspace(workspace_id)
        result = await self.session.execute(
            select(BrandPolicy)
            .where(
                BrandPolicy.workspace_id == workspace_id,
                BrandPolicy.name == policy_name,
            )
            .options(selectinload(BrandPolicy.guidelines))
            .order_by(BrandPolicy.version.asc())
        )
        versions = list(result.scalars().all())
        if not versions:
            raise NotFoundError("BrandPolicy (name)", policy_name)
        return versions

    async def update_policy_metadata(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        data: PolicyUpdate,
        actor_id: str,
    ) -> BrandPolicy:
        """Update name/description of a DRAFT policy. Active policies cannot be edited."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._require_draft(policy)

        changed: dict[str, Any] = {}
        if data.name is not None and data.name != policy.name:
            changed["name_before"] = policy.name
            changed["name_after"] = data.name
            policy.name = data.name
        if data.description is not None and data.description != policy.description:
            changed["description_updated"] = True
            policy.description = data.description

        if not changed:
            return policy  # No-op — nothing to record

        try:
            await self.session.flush()
        except IntegrityError as err:
            await self.session.rollback()
            raise ConflictError(
                f"A policy named '{data.name}' at version {policy.version} already exists in this workspace."
            ) from err

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_UPDATED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(policy.id),
            workspace_id=workspace_id,
            event_payload=changed,
        )
        return policy

    async def create_new_version(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        actor_id: str,
        new_description: str | None = None,
    ) -> BrandPolicy:
        """Create a new DRAFT version based on an existing ACTIVE policy.

        Copies all guidelines from the source into the new version's draft.
        The source policy must be ACTIVE; callers cannot fork from DRAFT or DEPRECATED.
        """
        source = await self._require_policy(workspace_id, policy_id)
        if source.status != PolicyStatus.ACTIVE:
            raise ValidationError(
                f"New versions can only be forked from ACTIVE policies; "
                f"source policy is '{source.status.value}'."
            )

        # Determine next version number for this policy name within the workspace
        result = await self.session.execute(
            select(func.max(BrandPolicy.version)).where(
                BrandPolicy.workspace_id == workspace_id,
                BrandPolicy.name == source.name,
            )
        )
        max_version = result.scalar_one() or 0
        next_version = max_version + 1

        new_policy = BrandPolicy(
            workspace_id=workspace_id,
            name=source.name,
            description=new_description if new_description is not None else source.description,
            version=next_version,
            status=PolicyStatus.DRAFT,
            created_by_id=actor_id,
        )
        self.session.add(new_policy)
        await self.session.flush()

        # Copy guidelines from source version
        for g in source.guidelines:
            copied = PolicyGuideline(
                policy_id=new_policy.id,
                category=g.category,
                title=g.title,
                rule_text=g.rule_text,
                examples_approved=list(g.examples_approved),
                examples_prohibited=list(g.examples_prohibited),
                severity_default=g.severity_default,
                is_mandatory=g.is_mandatory,
                rule_config=dict(g.rule_config) if g.rule_config else {},
            )
            self.session.add(copied)

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_CREATED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(new_policy.id),
            workspace_id=workspace_id,
            event_payload={
                "name": new_policy.name,
                "version": new_policy.version,
                "forked_from_id": str(source.id),
                "forked_from_version": source.version,
                "guidelines_copied": len(source.guidelines),
            },
        )

        # Reload with guidelines
        return await self._require_policy(workspace_id, new_policy.id)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    async def activate_policy(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        actor_id: str,
    ) -> BrandPolicy:
        """Transition a DRAFT policy to ACTIVE.

        Requires at least one guideline. Other versions of the same name
        already in ACTIVE status are automatically deprecated.
        """
        policy = await self._require_policy(workspace_id, policy_id)

        # Validate the transition is legal BEFORE checking guideline count so that
        # ARCHIVED / DEPRECATED / already-ACTIVE policies get a transition error,
        # not a misleading "add a guideline" message.
        allowed = _VALID_TRANSITIONS.get(policy.status, set())
        if PolicyStatus.ACTIVE not in allowed:
            allowed_str = (
                ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
                if allowed
                else "none (terminal state)"
            )
            raise ValidationError(
                f"Cannot transition policy from '{policy.status.value}' to 'active'. "
                f"Allowed transitions from '{policy.status.value}': {allowed_str}."
            )

        # Count guidelines (already loaded via selectinload)
        if len(policy.guidelines) == 0:
            raise ValidationError(
                "A policy must contain at least one guideline before it can be activated."
            )

        policy.status = PolicyStatus.ACTIVE

        # Deprecate any other ACTIVE versions of the same policy name in this workspace
        other_active_result = await self.session.execute(
            select(BrandPolicy).where(
                BrandPolicy.workspace_id == workspace_id,
                BrandPolicy.name == policy.name,
                BrandPolicy.id != policy.id,
                BrandPolicy.status == PolicyStatus.ACTIVE,
            )
        )
        deprecated_ids = []
        for other in other_active_result.scalars().all():
            other.status = PolicyStatus.DEPRECATED
            deprecated_ids.append(str(other.id))
            await self.audit.record_event(
                event_type=AuditEventType.POLICY_DEPRECATED,
                actor_id=actor_id,
                resource_type="BrandPolicy",
                resource_id=str(other.id),
                workspace_id=workspace_id,
                event_payload={
                    "reason": f"Auto-deprecated when version {policy.version} was activated",
                    "superseded_by": str(policy.id),
                },
            )

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_PUBLISHED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(policy.id),
            workspace_id=workspace_id,
            event_payload={
                "name": policy.name,
                "version": policy.version,
                "auto_deprecated_versions": deprecated_ids,
            },
        )
        return policy

    async def deprecate_policy(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        actor_id: str,
        reason: str,
    ) -> BrandPolicy:
        """Transition an ACTIVE policy to DEPRECATED."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._apply_transition(policy, PolicyStatus.DEPRECATED)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_DEPRECATED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(policy.id),
            workspace_id=workspace_id,
            event_payload={"reason": reason, "name": policy.name, "version": policy.version},
        )
        return policy

    async def archive_policy(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        actor_id: str,
    ) -> BrandPolicy:
        """Transition a policy to ARCHIVED (terminal state)."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._apply_transition(policy, PolicyStatus.ARCHIVED)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.POLICY_ARCHIVED,
            actor_id=actor_id,
            resource_type="BrandPolicy",
            resource_id=str(policy.id),
            workspace_id=workspace_id,
            event_payload={"name": policy.name, "version": policy.version},
        )
        return policy

    # ------------------------------------------------------------------
    # Guideline operations
    # ------------------------------------------------------------------

    async def _add_guideline_to_policy(
        self,
        policy: BrandPolicy,
        data: GuidelineCreate,
        actor_id: str,
        *,
        flush: bool = True,
    ) -> PolicyGuideline:
        """Internal: add a guideline row to a policy (caller is responsible for draft check)."""
        guideline = PolicyGuideline(
            policy_id=policy.id,
            category=data.category,
            title=data.title,
            rule_text=data.rule_text,
            examples_approved=data.examples_approved,
            examples_prohibited=data.examples_prohibited,
            severity_default=data.severity_default,
            is_mandatory=data.is_mandatory,
            rule_config=data.rule_config if data.rule_config else {},
        )
        self.session.add(guideline)
        if flush:
            await self.session.flush()
        return guideline

    async def add_guideline(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        data: GuidelineCreate,
        actor_id: str,
    ) -> PolicyGuideline:
        """Add a guideline to a DRAFT policy."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._require_draft(policy)

        guideline = await self._add_guideline_to_policy(policy, data, actor_id, flush=True)

        await self.audit.record_event(
            event_type=AuditEventType.GUIDELINE_ADDED,
            actor_id=actor_id,
            resource_type="PolicyGuideline",
            resource_id=str(guideline.id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "category": data.category.value,
                "title": data.title,
                "severity": data.severity_default.value,
            },
        )
        return guideline

    async def update_guideline(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        guideline_id: uuid.UUID,
        data: GuidelineUpdate,
        actor_id: str,
    ) -> PolicyGuideline:
        """Update fields on a guideline; policy must be in DRAFT status."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._require_draft(policy)
        guideline = await self._require_guideline(policy_id, guideline_id)

        changed: dict[str, Any] = {}
        if data.category is not None and data.category != guideline.category:
            changed["category"] = data.category.value
            guideline.category = data.category
        if data.title is not None and data.title != guideline.title:
            changed["title"] = data.title
            guideline.title = data.title
        if data.rule_text is not None and data.rule_text != guideline.rule_text:
            changed["rule_text_updated"] = True
            guideline.rule_text = data.rule_text
        if data.examples_approved is not None:
            changed["examples_approved_updated"] = True
            guideline.examples_approved = data.examples_approved
        if data.examples_prohibited is not None:
            changed["examples_prohibited_updated"] = True
            guideline.examples_prohibited = data.examples_prohibited
        if (
            data.severity_default is not None
            and data.severity_default != guideline.severity_default
        ):
            changed["severity_default"] = data.severity_default.value
            guideline.severity_default = data.severity_default
        if data.is_mandatory is not None and data.is_mandatory != guideline.is_mandatory:
            changed["is_mandatory"] = data.is_mandatory
            guideline.is_mandatory = data.is_mandatory
        if data.rule_config is not None:
            changed["rule_config_updated"] = True
            guideline.rule_config = data.rule_config

        if not changed:
            return guideline

        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.GUIDELINE_UPDATED,
            actor_id=actor_id,
            resource_type="PolicyGuideline",
            resource_id=str(guideline.id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "changes": changed,
            },
        )
        return guideline

    async def delete_guideline(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
        guideline_id: uuid.UUID,
        actor_id: str,
    ) -> None:
        """Delete a guideline from a DRAFT policy."""
        policy = await self._require_policy(workspace_id, policy_id)
        self._require_draft(policy)
        guideline = await self._require_guideline(policy_id, guideline_id)

        await self.session.delete(guideline)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.GUIDELINE_DELETED,
            actor_id=actor_id,
            resource_type="PolicyGuideline",
            resource_id=str(guideline_id),
            workspace_id=workspace_id,
            event_payload={
                "policy_id": str(policy.id),
                "policy_version": policy.version,
                "category": guideline.category.value,
                "title": guideline.title,
            },
        )

    async def list_guidelines(
        self,
        workspace_id: uuid.UUID,
        policy_id: uuid.UUID,
    ) -> list[PolicyGuideline]:
        """Return all guidelines for a policy, ordered by category then title."""
        policy = await self._require_policy(workspace_id, policy_id)
        result = await self.session.execute(
            select(PolicyGuideline)
            .where(PolicyGuideline.policy_id == policy.id)
            .order_by(PolicyGuideline.category, PolicyGuideline.title)
        )
        return list(result.scalars().all())
