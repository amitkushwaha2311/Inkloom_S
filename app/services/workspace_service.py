"""Inkloom Sentinel - Workspace Management Service.

Handles workspace creation and membership operations with role enforcement.

Role hierarchy (highest to lowest privilege):
  OWNER > ADMIN > REVIEWER > CONTRIBUTOR > VIEWER

Permission rules:
  - Create workspace: any authenticated user (becomes OWNER)
  - Add/remove members: OWNER or ADMIN only
  - Change role: OWNER only (cannot change another OWNER without first demoting)
  - Read workspace: any active member
  - OWNER cannot be demoted by ADMIN — only by another OWNER
"""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import AuditEventType, WorkspaceRole
from app.domain.models.workspace import BrandWorkspace, WorkspaceMember
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# Roles that can manage membership
_MEMBERSHIP_MANAGERS = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}
# Only owners can change roles
_ROLE_MANAGERS = {WorkspaceRole.OWNER}


def _slugify(name: str) -> str:
    """Convert a workspace name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:100]


class WorkspaceService:
    """Manages workspace lifecycle and membership with role-based access control."""

    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _require_workspace(self, workspace_id: uuid.UUID) -> BrandWorkspace:
        result = await self.session.execute(
            select(BrandWorkspace).where(BrandWorkspace.id == workspace_id)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            raise NotFoundError("BrandWorkspace", str(workspace_id))
        return ws

    async def _require_membership(self, workspace_id: uuid.UUID, user_id: str) -> WorkspaceMember:
        """Return membership if active, ensuring workspace exists (404 if not found)."""
        await self._require_workspace(workspace_id)
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active == True,  # noqa: E712
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise ForbiddenError("You are not a member of this workspace.")
        return member

    async def _require_role(
        self,
        workspace_id: uuid.UUID,
        user_id: str,
        minimum_roles: set[WorkspaceRole],
    ) -> WorkspaceMember:
        """Ensure the calling user has at least one of the required roles."""
        member = await self._require_membership(workspace_id, user_id)
        if member.role not in minimum_roles:
            raise ForbiddenError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value for r in minimum_roles)}. "
                f"Your current role is '{member.role.value}'."
            )
        return member

    # ------------------------------------------------------------------
    # Workspace CRUD
    # ------------------------------------------------------------------

    async def create_workspace(
        self,
        name: str,
        description: str | None,
        actor_user_id: str,
        actor_email: str,
    ) -> BrandWorkspace:
        """Create a workspace and automatically add the creator as OWNER."""
        base_slug = _slugify(name)
        slug = base_slug

        ws = BrandWorkspace(name=name, description=description, slug=slug)
        self.session.add(ws)

        try:
            await self.session.flush()
        except IntegrityError:
            # Slug collision — append a random suffix
            import secrets as _secrets  # noqa: PLC0415

            await self.session.rollback()
            slug = f"{base_slug}-{_secrets.token_hex(4)}"
            ws = BrandWorkspace(name=name, description=description, slug=slug)
            self.session.add(ws)
            await self.session.flush()

        # Add creator as OWNER
        member = WorkspaceMember(
            workspace_id=ws.id,
            user_id=actor_user_id,
            email=actor_email,
            role=WorkspaceRole.OWNER,
        )
        self.session.add(member)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.WORKSPACE_CREATED,
            actor_id=actor_user_id,
            resource_type="BrandWorkspace",
            resource_id=str(ws.id),
            workspace_id=ws.id,
            event_payload={"name": name, "slug": slug},
        )
        logger.info("workspace_created", workspace_id=str(ws.id), actor=actor_user_id)
        return ws

    async def get_workspace(self, workspace_id: uuid.UUID, actor_user_id: str) -> BrandWorkspace:
        """Return workspace detail if actor is an active member."""
        await self._require_membership(workspace_id, actor_user_id)
        return await self._require_workspace(workspace_id)

    async def list_my_workspaces(self, actor_user_id: str) -> list[BrandWorkspace]:
        """Return all workspaces the actor is an active member of."""
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == actor_user_id,
                WorkspaceMember.is_active == True,  # noqa: E712
            )
        )
        memberships = list(result.scalars().all())
        workspaces = []
        for m in memberships:
            ws_result = await self.session.execute(
                select(BrandWorkspace).where(BrandWorkspace.id == m.workspace_id)
            )
            ws = ws_result.scalar_one_or_none()
            if ws:
                workspaces.append(ws)
        return workspaces

    # ------------------------------------------------------------------
    # Membership management
    # ------------------------------------------------------------------

    async def list_members(
        self, workspace_id: uuid.UUID, actor_user_id: str
    ) -> list[WorkspaceMember]:
        """List all active members. Requires membership."""
        await self._require_membership(workspace_id, actor_user_id)
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
            )
            .order_by(WorkspaceMember.joined_at)
        )
        return list(result.scalars().all())

    async def add_member(
        self,
        workspace_id: uuid.UUID,
        target_user_id: str,
        target_email: str,
        role: WorkspaceRole,
        actor_user_id: str,
    ) -> WorkspaceMember:
        """Add a new member. Requires OWNER or ADMIN role.

        Silently reactivates a previously removed member if they rejoin.
        OWNERs can only be added by other OWNERs.
        """
        await self._require_role(workspace_id, actor_user_id, _MEMBERSHIP_MANAGERS)

        # Only OWNERs can add another OWNER
        if role == WorkspaceRole.OWNER:
            await self._require_role(workspace_id, actor_user_id, _ROLE_MANAGERS)

        # Check if member already exists
        existing_result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == target_user_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            if existing.is_active:
                raise ConflictError(f"User '{target_email}' is already a member of this workspace.")
            # Reactivate
            existing.is_active = True
            existing.role = role
            await self.session.flush()
            member = existing
        else:
            member = WorkspaceMember(
                workspace_id=workspace_id,
                user_id=target_user_id,
                email=target_email,
                role=role,
            )
            self.session.add(member)
            await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.WORKSPACE_MEMBER_ADDED,
            actor_id=actor_user_id,
            resource_type="WorkspaceMember",
            resource_id=str(member.id),
            workspace_id=workspace_id,
            event_payload={
                "target_user_id": target_user_id,
                "target_email": target_email,
                "role": role.value,
            },
        )
        return member

    async def change_member_role(
        self,
        workspace_id: uuid.UUID,
        target_user_id: str,
        new_role: WorkspaceRole,
        actor_user_id: str,
    ) -> WorkspaceMember:
        """Change a member's role. Only OWNERs may change roles."""
        await self._require_role(workspace_id, actor_user_id, _ROLE_MANAGERS)

        target_result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == target_user_id,
                WorkspaceMember.is_active == True,  # noqa: E712
            )
        )
        target = target_result.scalar_one_or_none()
        if target is None:
            raise NotFoundError("WorkspaceMember", target_user_id)

        # Prevent self-demotion if actor is the last owner
        if target.user_id == actor_user_id and new_role != WorkspaceRole.OWNER:
            owner_count_result = await self.session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.is_active == True,  # noqa: E712
                )
            )
            owner_count = len(list(owner_count_result.scalars().all()))
            if owner_count <= 1:
                raise ValidationError(
                    "Cannot demote the last OWNER of a workspace. " "Assign another OWNER first."
                )

        old_role = target.role
        target.role = new_role
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.WORKSPACE_MEMBER_ROLE_CHANGED,
            actor_id=actor_user_id,
            resource_type="WorkspaceMember",
            resource_id=str(target.id),
            workspace_id=workspace_id,
            event_payload={
                "target_user_id": target_user_id,
                "old_role": old_role.value,
                "new_role": new_role.value,
            },
        )
        return target

    async def remove_member(
        self,
        workspace_id: uuid.UUID,
        target_user_id: str,
        actor_user_id: str,
    ) -> None:
        """Soft-remove a member. OWNER or ADMIN required.

        OWNERs cannot be removed by ADMINs. The last OWNER cannot be removed.
        """
        actor_member = await self._require_role(workspace_id, actor_user_id, _MEMBERSHIP_MANAGERS)

        target_result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == target_user_id,
                WorkspaceMember.is_active == True,  # noqa: E712
            )
        )
        target = target_result.scalar_one_or_none()
        if target is None:
            raise NotFoundError("WorkspaceMember", target_user_id)

        # Only OWNERs can remove other OWNERs
        if target.role == WorkspaceRole.OWNER and actor_member.role != WorkspaceRole.OWNER:
            raise ForbiddenError("Only a workspace OWNER can remove another OWNER.")

        # Protect last owner
        if target.role == WorkspaceRole.OWNER:
            owner_count_result = await self.session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.is_active == True,  # noqa: E712
                )
            )
            owner_count = len(list(owner_count_result.scalars().all()))
            if owner_count <= 1:
                raise ValidationError("Cannot remove the last OWNER of a workspace.")

        target.is_active = False
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.WORKSPACE_MEMBER_REMOVED,
            actor_id=actor_user_id,
            resource_type="WorkspaceMember",
            resource_id=str(target.id),
            workspace_id=workspace_id,
            event_payload={
                "target_user_id": target_user_id,
                "role": target.role.value,
            },
        )

    async def verify_workspace_access(
        self,
        workspace_id: uuid.UUID,
        actor_user_id: str,
        *,
        minimum_roles: set[WorkspaceRole] | None = None,
    ) -> WorkspaceMember:
        """General access check. If minimum_roles is None, any active member passes."""
        if minimum_roles:
            return await self._require_role(workspace_id, actor_user_id, minimum_roles)
        return await self._require_membership(workspace_id, actor_user_id)
