"""Rate limiting service for authentication endpoints."""

import time
from typing import Dict, List, Tuple

# In-memory storage for rate limiting
# key -> list of attempt timestamps
_rate_limits: Dict[str, List[float]] = {}


def check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Check if a rate limit has been exceeded for a given key.

    Args:
        key: Unique identifier for the rate limit (e.g., "login:username" or "register:ip")
        max_attempts: Maximum number of attempts allowed within the window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_allowed: bool, remaining_attempts: int)
    """
    now = time.time()
    cutoff = now - window_seconds

    # Clean up old timestamps (lazy cleanup)
    if key in _rate_limits:
        _rate_limits[key] = [ts for ts in _rate_limits[key] if ts > cutoff]
    else:
        _rate_limits[key] = []

    # Check if limit exceeded
    current_attempts = len(_rate_limits[key])

    if current_attempts >= max_attempts:
        return False, 0

    # Record this attempt
    _rate_limits[key].append(now)
    remaining = max_attempts - current_attempts - 1

    return True, remaining


def reset_rate_limit(key: str) -> None:
    """
    Clear rate limit for a key (called on successful login).

    Args:
        key: Unique identifier for the rate limit
    """
    if key in _rate_limits:
        del _rate_limits[key]


def get_retry_after(key: str, window_seconds: int) -> int:
    """
    Get seconds until the rate limit window expires.

    Args:
        key: Unique identifier for the rate limit
        window_seconds: Time window in seconds

    Returns:
        Seconds until oldest attempt expires (0 if no attempts or already expired)
    """
    if key not in _rate_limits or not _rate_limits[key]:
        return 0

    now = time.time()
    oldest_attempt = min(_rate_limits[key])
    retry_after = int(oldest_attempt + window_seconds - now)

    return max(0, retry_after)
