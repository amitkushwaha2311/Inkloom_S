"""Inkloom Sentinel - Foundational Security Utilities.

Cryptographic helpers, token generation, constant-time comparison,
and privacy-preserving audit hashing.
"""

import hashlib
import hmac
import secrets


def generate_secure_token(n_bytes: int = 32) -> str:
    """Generate a cryptographically strong URL-safe random string."""
    return secrets.token_urlsafe(n_bytes)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def hash_sensitive_identifier(identifier: str | None, salt: str = "inkloom-audit-salt") -> str | None:
    """Produce a one-way deterministic SHA-256 hash of an identifier (e.g. client IP).

    Prevents raw IP or sensitive identifiers from persisting in plaintext
    while preserving forensic correlation capability.
    """
    if not identifier:
        return None
    salted = f"{salt}:{identifier}".encode()
    return hashlib.sha256(salted).hexdigest()
