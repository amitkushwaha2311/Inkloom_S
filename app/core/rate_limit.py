"""Inkloom Sentinel - In-Memory Sliding-Window Rate Limiter.

Provides abuse prevention and rate-limiting controls for:
- Authentication endpoints (login, register, refresh) to mitigate brute-force attacks.
- Expensive verification operations (deterministic engine, semantic review, unified summary)
  to prevent denial-of-service and resource exhaustion.
"""

import asyncio
import time
from collections import defaultdict

from app.core.errors import RateLimitExceededError


class SlidingWindowRateLimiter:
    """Thread-safe, in-memory sliding window rate limiter."""

    def __init__(self):
        self._lock = asyncio.Lock()
        # Key -> list of timestamps
        self._records: dict[str, list[float]] = defaultdict(list)

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        """Check if request count for key within window_seconds exceeds max_requests.

        Raises:
            RateLimitExceededError: If request count exceeds max_requests within window.
        """
        now = time.time()
        cutoff = now - window_seconds

        async with self._lock:
            # Filter timestamps outside the sliding window
            timestamps = [ts for ts in self._records[key] if ts > cutoff]
            if len(timestamps) >= max_requests:
                # Calculate oldest timestamp within the window to estimate retry-after
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + window_seconds - now))
                raise RateLimitExceededError(
                    message=f"Rate limit of {max_requests} requests per {window_seconds}s exceeded.",
                    retry_after=retry_after,
                )

            timestamps.append(now)
            self._records[key] = timestamps

    async def reset(self) -> None:
        """Clear all rate limit tracking records."""
        async with self._lock:
            self._records.clear()


# Global limiter instances
auth_rate_limiter = SlidingWindowRateLimiter()
expensive_ops_limiter = SlidingWindowRateLimiter()
