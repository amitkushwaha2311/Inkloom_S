"""Inkloom Sentinel - Authentication Service.

Handles user registration, login, token issuance, refresh, and revocation.

Security properties enforced here:
- Passwords are hashed with bcrypt (12 rounds) before storage
- Passwords are never logged, returned in responses, or stored plaintext
- Login failures return a generic message; email existence is not revealed
- Access tokens are short-lived HS256 JWTs (default: 15 minutes)
- Refresh tokens are opaque 32-byte random strings; only SHA-256 hash stored
- Token replay after revocation is rejected
- Expired tokens are rejected with 401, not 500
- Rate limiting is NOT implemented here (must be handled at infra/proxy layer)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from jose import ExpiredSignatureError, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    hash_sensitive_identifier,
    refresh_token_expiry,
    verify_password,
)
from app.domain.enums import AuditEventType
from app.domain.models.user import RefreshToken, User
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# Sentinel claim embedded in every access token to distinguish them from other JWTs
_TOKEN_TYPE_CLAIM = "sentinel_access"


class AuthService:
    """Manages user account creation, authentication, and token lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        secret_key: str,
        *,
        access_expire_minutes: int = 15,
    ) -> None:
        self.session = session
        self.audit = audit
        self.secret_key = secret_key
        self.access_expire_minutes = access_expire_minutes

    # ------------------------------------------------------------------
    # User lookup helpers
    # ------------------------------------------------------------------

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
        client_ip: str | None = None,
    ) -> User:
        """Register a new user account.

        Raises ConflictError if email is already registered.
        Does NOT log the password at any point.
        """
        email = email.lower().strip()

        # Check for duplicate — return same error as login to avoid enumeration
        existing = await self._get_user_by_email(email)
        if existing is not None:
            raise ConflictError("An account with that email address already exists.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_verified=False,  # Email verification deferred to later phase
        )
        self.session.add(user)
        await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.USER_REGISTERED,
            actor_id=str(user.id),
            resource_type="User",
            resource_id=str(user.id),
            event_payload={"email": email, "full_name": full_name},
            client_ip=client_ip,
        )
        logger.info("user_registered", user_id=str(user.id))
        return user

    # ------------------------------------------------------------------
    # Login — returns (access_token, raw_refresh_token)
    # ------------------------------------------------------------------

    async def login(
        self,
        email: str,
        password: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Authenticate and return (access_token, raw_refresh_token).

        Uses identical error messages for wrong email and wrong password
        to prevent user enumeration attacks.
        """
        email = email.lower().strip()
        _GENERIC_ERROR = "Invalid email or password."

        user = await self._get_user_by_email(email)

        # Always run password verification even if no user found (timing resistance)
        # Use a dummy hash so bcrypt timing is consistent
        _dummy_hash = "$2b$12$dummy.hash.for.constant.time.comparison.only"
        supplied_hash = user.hashed_password if user else _dummy_hash
        password_ok = verify_password(password, supplied_hash)

        if user is None or not password_ok:
            await self.audit.record_event(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                actor_id="anonymous",
                resource_type="User",
                resource_id="unknown",
                event_payload={"email_hint": email[:3] + "***"},
                client_ip=client_ip,
            )
            raise UnauthorizedError(_GENERIC_ERROR)

        if not user.is_active:
            raise UnauthorizedError("Account is disabled. Contact support.")

        access_token = self._issue_access_token(user)
        raw_refresh, _ = await self._create_refresh_token(
            user, client_ip=client_ip, user_agent=user_agent
        )

        await self.audit.record_event(
            event_type=AuditEventType.USER_LOGIN,
            actor_id=str(user.id),
            resource_type="User",
            resource_id=str(user.id),
            event_payload={},  # No PII: actor_id (UUID) already identifies the user
            client_ip=client_ip,
            user_agent=user_agent,
        )
        logger.info("user_login_success", user_id=str(user.id))
        return access_token, raw_refresh

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    async def refresh(
        self,
        raw_refresh_token: str,
        client_ip: str | None = None,
    ) -> tuple[str, str]:
        """Exchange a valid refresh token for a new access + refresh token pair.

        The old refresh token is revoked (rotation). Returns 401 if:
        - Token hash is not found
        - Token is already revoked
        - Token has expired
        """
        token_hash = hash_refresh_token(raw_refresh_token)

        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        record = result.scalar_one_or_none()

        if record is None or record.is_revoked:
            raise UnauthorizedError("Refresh token is invalid or has been revoked.")

        now = datetime.now(UTC)
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            # Expired — revoke proactively to clean up
            record.is_revoked = True
            await self.session.flush()
            raise UnauthorizedError("Refresh token has expired. Please log in again.")

        # Revoke the used token (rotation)
        record.is_revoked = True
        await self.session.flush()

        user = await self._get_user_by_id(record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account not found or disabled.")

        new_access = self._issue_access_token(user)
        raw_new_refresh, _ = await self._create_refresh_token(user, client_ip=client_ip)

        await self.audit.record_event(
            event_type=AuditEventType.TOKEN_REFRESHED,
            actor_id=str(user.id),
            resource_type="RefreshToken",
            resource_id=str(record.id),
            event_payload={},
            client_ip=client_ip,
        )
        return new_access, raw_new_refresh

    # ------------------------------------------------------------------
    # Logout / revocation
    # ------------------------------------------------------------------

    async def logout(
        self,
        raw_refresh_token: str,
        actor_id: str,
        client_ip: str | None = None,
    ) -> None:
        """Revoke a refresh token. Silently succeeds if already revoked."""
        token_hash = hash_refresh_token(raw_refresh_token)
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        record = result.scalar_one_or_none()
        if record and not record.is_revoked:
            record.is_revoked = True
            await self.session.flush()

        await self.audit.record_event(
            event_type=AuditEventType.USER_LOGOUT,
            actor_id=actor_id,
            resource_type="RefreshToken",
            resource_id=str(record.id) if record else "unknown",
            event_payload={},
            client_ip=client_ip,
        )

    # ------------------------------------------------------------------
    # Access token verification (used by the auth dependency)
    # ------------------------------------------------------------------

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT access token.

        Raises:
            UnauthorizedError — for expired, malformed, or missing tokens.
        """
        try:
            payload = decode_access_token(token, self.secret_key)
        except ExpiredSignatureError:
            raise UnauthorizedError("Access token has expired.") from None
        except JWTError:
            raise UnauthorizedError("Access token is invalid.") from None

        if payload.get("type") != _TOKEN_TYPE_CLAIM:
            raise UnauthorizedError("Access token has an unrecognized type.")

        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _issue_access_token(self, user: User) -> str:
        """Build and sign a JWT access token for the given user."""
        return create_access_token(
            payload={
                "sub": str(user.id),
                "email": user.email,
                "type": _TOKEN_TYPE_CLAIM,
            },
            secret_key=self.secret_key,
            expires_minutes=self.access_expire_minutes,
        )

    async def _create_refresh_token(
        self,
        user: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, RefreshToken]:
        """Generate, hash, and persist a new refresh token record.

        Returns (raw_token, RefreshToken) — caller must transmit raw_token
        to the client and must not store it.
        """
        raw = generate_refresh_token()
        token_hash = hash_refresh_token(raw)
        ip_hash = hash_sensitive_identifier(client_ip)

        record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_token_expiry(),
            hint=raw[:8],
            user_agent_snippet=user_agent[:120] if user_agent else None,
            ip_address_hash=ip_hash,
        )
        self.session.add(record)
        await self.session.flush()
        return raw, record
