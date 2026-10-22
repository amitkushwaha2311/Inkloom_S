"""Inkloom Sentinel - Auth & User Pydantic Schemas."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Account email address")
    password: Annotated[
        str,
        Field(min_length=8, max_length=128, description="Must be at least 8 characters"),
    ]
    full_name: Annotated[str, Field(max_length=160)] | None = None

    @field_validator("password")
    @classmethod
    def password_must_have_complexity(cls, v: str) -> str:
        """Require at least one digit and one letter."""
        has_digit = any(c.isdigit() for c in v)
        has_alpha = any(c.isalpha() for c in v)
        if not (has_digit and has_alpha):
            raise ValueError("Password must contain at least one letter and one digit.")
        return v


class UserLoginRequest(BaseModel):
    """OAuth2-compatible form fields or JSON body for token endpoint."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Standard OAuth2-style token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, v: str) -> str:
        has_digit = any(c.isdigit() for c in v)
        has_alpha = any(c.isalpha() for c in v)
        if not (has_digit and has_alpha):
            raise ValueError("Password must contain at least one letter and one digit.")
        return v
