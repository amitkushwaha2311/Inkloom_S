"""Inkloom Sentinel - SSRF & URL Protection Utilities.

Provides strict URL validation to prevent Server-Side Request Forgery (SSRF)
attacks when registering or evaluating external evidence source URLs.
"""

import ipaddress
from urllib.parse import urlparse

from app.core.errors import ValidationError

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
}

_BLOCKED_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".arpa",
)


def is_ip_private_or_restricted(ip_str: str) -> bool:
    """Return True if the IP address string is private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        pass

    # Check for decimal/integer IP representation (e.g. "2130706433" -> 127.0.0.1)
    if ip_str.isdigit():
        try:
            val = int(ip_str)
            if 0 <= val <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(val)
                return (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                    or ip.is_unspecified
                )
            return True
        except (ValueError, OverflowError):
            return True

    # Check for hex IP representation (e.g. "0x7f000001")
    if ip_str.lower().startswith("0x"):
        try:
            val = int(ip_str, 16)
            if 0 <= val <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(val)
                return (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                    or ip.is_unspecified
                )
            return True
        except (ValueError, OverflowError):
            return True

    return False


def validate_safe_url(url: str | None) -> str | None:
    """Validate that a URL is safe from SSRF vulnerabilities.

    Rules:
    - Scheme must be strictly 'http' or 'https'.
    - Hostname must be present and well-formed.
    - Loopback, private (RFC 1918), link-local (169.254.0.0/16, AWS metadata),
      IPv6 loopback/private, and internal/metadata hostnames are strictly rejected.

    Raises:
        ValidationError: If the URL violates any safety check.

    Returns:
        The normalized URL string, or None if url is None or empty.
    """
    if not url or not url.strip():
        return None

    cleaned_url = url.strip()
    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise ValidationError(f"Invalid URL structure: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValidationError(
            f"Unsupported URL scheme '{scheme}'. Only http and https URLs are permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("URL must contain a valid hostname.")

    hostname_lower = hostname.lower()

    if hostname_lower in _BLOCKED_HOSTNAMES or any(
        hostname_lower.endswith(suffix) for suffix in _BLOCKED_SUFFIXES
    ):
        raise ValidationError(
            f"URL host '{hostname}' is not permitted (restricted or internal domain)."
        )

    # Check if hostname is an explicit IP literal
    if is_ip_private_or_restricted(hostname_lower):
        raise ValidationError(
            f"URL target '{hostname}' is a private, loopback, or restricted IP address."
        )

    # If port is specified, ensure it is standard web port (optional safeguard)
    if parsed.port and parsed.port not in (80, 443, 8080, 8443):
        raise ValidationError(f"Port {parsed.port} is not permitted for evidence source URLs.")

    return cleaned_url
