"""Inkloom Sentinel - Security Utilities.

Cryptographic helpers covering:
- Password hashing and verification (bcrypt via passlib)
- JWT access token creation and validation (HS256, python-jose)
- Opaque refresh token generation and hashing
- Constant-time comparison
- Privacy-preserving audit hashing

Security properties:
- Access tokens are HS256-signed JWTs with 15-minute lifetime
- Refresh tokens are 32-byte cryptographically random opaque strings
- Only the SHA-256 hash of a refresh token is persisted (server-side)
- bcrypt work factor is configurable; default 12 rounds
- Passwords are NEVER logged or included in error responses
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import jwt

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# bcrypt with 12 rounds is the recommended baseline for interactive logins.
# Using bcrypt directly avoids deprecated passlib dependencies.
_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password.

    Never log or return the input to this function.
    """
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Uses constant-time comparison internally via bcrypt.checkpw.
    Returns False (not raises) on mismatch or hash format error.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001 — bcrypt raises ValueError on malformed hashes
        return False


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 15


def create_access_token(
    payload: dict[str, Any],
    secret_key: str,
    *,
    expires_minutes: int = _ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Create a signed HS256 JWT access token.

    Args:
        payload: Claims to embed (must not contain sensitive data like passwords).
        secret_key: Application secret used for signing.
        expires_minutes: Lifetime in minutes from now. Default 15.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    claims = {
        **payload,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(claims, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises:
        ExpiredSignatureError: Token has expired.
        JWTError: Token is malformed, has invalid signature, or is missing claims.
    """
    return jwt.decode(token, secret_key, algorithms=[_ALGORITHM])


# ---------------------------------------------------------------------------
# Opaque refresh tokens
# ---------------------------------------------------------------------------

_REFRESH_TOKEN_BYTES = 32
_REFRESH_TOKEN_EXPIRE_DAYS = 7


def generate_refresh_token() -> str:
    """Generate a 32-byte cryptographically random URL-safe token string."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a raw refresh token.

    Only this hash is stored in the database — the raw token is discarded.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    """Return a UTC datetime representing when a newly issued refresh token expires."""
    return datetime.now(UTC) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)


# ---------------------------------------------------------------------------
# Generic utilities
# ---------------------------------------------------------------------------


def generate_secure_token(n_bytes: int = 32) -> str:
    """Generate a cryptographically strong URL-safe random string."""
    return secrets.token_urlsafe(n_bytes)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def hash_sensitive_identifier(
    identifier: str | None, salt: str = "inkloom-audit-salt"
) -> str | None:
    """Produce a one-way deterministic SHA-256 hash of an identifier (e.g. client IP).

    Prevents raw IP or sensitive identifiers from persisting in plaintext
    while preserving forensic correlation capability.
    """
    if not identifier:
        return None
    salted = f"{salt}:{identifier}".encode()
    return hashlib.sha256(salted).hexdigest()
