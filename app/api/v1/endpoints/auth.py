"""Inkloom Sentinel - Authentication Endpoints.

Provides registration, login, token refresh, logout, and current user info.

Security notes:
- POST /register: creates account; does NOT auto-login
- POST /login: returns access + refresh tokens; credentials in JSON body (not URL)
- POST /refresh: rotates refresh token
- POST /logout: revokes refresh token server-side
- GET  /me: returns current user (requires valid access token)
- PATCH /me/password: change password with current-password verification
"""

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import (
    CurrentUser,
    get_auth_service,
    get_client_ip,
    get_user_agent,
)
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.core.rate_limit import auth_rate_limiter
from app.core.security import hash_password, verify_password
from app.domain.enums import AuditEventType
from app.domain.schemas.auth import (
    ChangePasswordRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Account",
    description=(
        "Create a new user account. Does not return tokens — call /login after registration. "
        "Passwords must be at least 8 characters with at least one letter and digit."
    ),
)
async def register(
    body: UserRegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    client_ip: str | None = Depends(get_client_ip),
) -> UserResponse:
    if settings.RATE_LIMIT_ENABLED:
        await auth_rate_limiter.check_rate_limit(
            key=f"auth:{client_ip or 'unknown'}",
            max_requests=settings.AUTH_RATE_LIMIT_MAX_REQUESTS,
        )
    user = await auth.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        client_ip=client_ip,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description=(
        "Authenticate with email and password. Returns a short-lived access token "
        "(15 min) and a 7-day refresh token. "
        "The access token is a signed JWT; the refresh token is opaque."
    ),
)
async def login(
    body: UserLoginRequest,
    auth: AuthService = Depends(get_auth_service),
    client_ip: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
) -> TokenResponse:
    if settings.RATE_LIMIT_ENABLED:
        await auth_rate_limiter.check_rate_limit(
            key=f"auth:{client_ip or 'unknown'}",
            max_requests=settings.AUTH_RATE_LIMIT_MAX_REQUESTS,
        )
    access_token, refresh_token = await auth.login(
        email=body.email,
        password=body.password,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Tokens",
    description=(
        "Exchange a valid refresh token for a new access + refresh token pair. "
        "The submitted refresh token is immediately revoked (rotation)."
    ),
)
async def refresh_tokens(
    body: RefreshRequest,
    auth: AuthService = Depends(get_auth_service),
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    if settings.RATE_LIMIT_ENABLED:
        await auth_rate_limiter.check_rate_limit(
            key=f"auth:{client_ip or 'unknown'}",
            max_requests=settings.AUTH_RATE_LIMIT_MAX_REQUESTS,
        )
    access_token, new_refresh = await auth.refresh(
        raw_refresh_token=body.refresh_token,
        client_ip=client_ip,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke a refresh token server-side. Safe to call even if already revoked.",
)
async def logout(
    body: LogoutRequest,
    current_user: CurrentUser,
    auth: AuthService = Depends(get_auth_service),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    await auth.logout(
        raw_refresh_token=body.refresh_token,
        actor_id=str(current_user.id),
        client_ip=client_ip,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User",
    description="Returns the authenticated user's profile. Requires a valid access token.",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change Password",
    description=(
        "Change the current user's password. "
        "Requires the existing password for verification. "
        "All existing refresh tokens remain valid — log out separately if needed."
    ),
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    if settings.RATE_LIMIT_ENABLED:
        await auth_rate_limiter.check_rate_limit(
            key=f"auth:{current_user.id}",
            max_requests=settings.AUTH_RATE_LIMIT_MAX_REQUESTS,
        )
    if not verify_password(body.current_password, current_user.hashed_password):
        raise UnauthorizedError("Current password is incorrect.")

    current_user.hashed_password = hash_password(body.new_password)
    # Flush the password update before recording the audit event so both
    # writes share the same transaction and either both commit or both roll back.
    await auth.session.flush()

    await auth.audit.record_event(
        event_type=AuditEventType.PASSWORD_CHANGED,
        actor_id=str(current_user.id),
        resource_type="User",
        resource_id=str(current_user.id),
        event_payload={},
    )
