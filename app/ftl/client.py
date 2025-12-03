"""HTTP client for fetching FTL data with retry, caching, and bulk fetch orchestration."""
import time
import requests
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .parsers import parse_pool_ids, parse_pool_html, parse_pool_results


# Base URL for FencingTimeLive
FTL_BASE_URL = "https://www.fencingtimelive.com"

# Default headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


class FTLHTTPError(Exception):
    """HTTP request failed after retries."""
    pass


class FTLParseError(Exception):
    """Parsing FTL response failed."""
    pass


# In-memory cache with TTL
class SimpleCache:
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 180):
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 180)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        expiry = time.time() + ttl
        with self._lock:
            self._cache[key] = (value, expiry)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()


# Global cache instance
_cache = SimpleCache(default_ttl=180)


def _build_url(path: str) -> str:
    """Build full URL from path."""
    return f"{FTL_BASE_URL}{path}"


def _fetch_with_retry(
    url: str,
    *,
    timeout: int = 10,
    max_retries: int = 3,
    backoff_base: float = 0.5
) -> str:
    """
    Fetch URL with exponential backoff retry logic.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay for exponential backoff in seconds

    Returns:
        Response text

    Raises:
        FTLHTTPError: If request fails after all retries
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)

            # Don't retry on 4xx errors (client errors)
            if 400 <= response.status_code < 500:
                raise FTLHTTPError(
                    f"HTTP {response.status_code} for URL: {url}"
                )

            response.raise_for_status()

            if not response.text:
                raise FTLHTTPError(f"Empty response from URL: {url}")

            return response.text

        except requests.Timeout as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = backoff_base * (2 ** attempt)
                time.sleep(delay)
            continue

        except requests.RequestException as e:
            last_exception = e
            # Retry on 5xx or network errors
            if attempt < max_retries - 1:
                delay = backoff_base * (2 ** attempt)
                time.sleep(delay)
            continue

    # All retries exhausted - preserve exception type info in message
    error_type = type(last_exception).__name__ if last_exception else "Unknown"
    raise FTLHTTPError(
        f"Failed to fetch URL after {max_retries} attempts ({error_type}): {url}"
    ) from last_exception


def fetch_html(url: str, timeout: int = 10) -> str:
    """
    Fetch HTML content from a URL (legacy interface, no retry).

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        The HTML content as a string

    Raises:
        ValueError: If the request fails or returns empty content
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {exc}") from exc

    if not response.text:
        raise ValueError("Empty response body")

    return response.text


def fetch_pool_ids_raw(
    event_id: str,
    pool_round_id: str,
    *,
    timeout: int = 10,
    force_refresh: bool = False
) -> str:
    """
    Fetch pool IDs HTML page with caching.

    Args:
        event_id: Event UUID
        pool_round_id: Pool round UUID
        timeout: Request timeout
        force_refresh: Bypass cache and force fresh fetch

    Returns:
        Raw HTML text

    Raises:
        FTLHTTPError: If fetch fails
    """
    path = f"/pools/scores/{event_id}/{pool_round_id}"
    url = _build_url(path)
    cache_key = f"pool_ids:{event_id}:{pool_round_id}"

    if not force_refresh:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    html = _fetch_with_retry(url, timeout=timeout)
    _cache.set(cache_key, html)
    return html


def fetch_pool_html_raw(
    event_id: str,
    pool_round_id: str,
    pool_id: str,
    *,
    timeout: int = 10,
    force_refresh: bool = False
) -> str:
    """
    Fetch individual pool HTML page with caching.

    Args:
        event_id: Event UUID
        pool_round_id: Pool round UUID
        pool_id: Pool UUID
        timeout: Request timeout
        force_refresh: Bypass cache and force fresh fetch

    Returns:
        Raw HTML text

    Raises:
        FTLHTTPError: If fetch fails
    """
    path = f"/pools/scores/{event_id}/{pool_round_id}/{pool_id}"
    url = _build_url(path) + "?dbut=true"
    cache_key = f"pool_html:{event_id}:{pool_round_id}:{pool_id}"

    if not force_refresh:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    html = _fetch_with_retry(url, timeout=timeout)
    _cache.set(cache_key, html)
    return html


def fetch_pool_results_raw(
    event_id: str,
    pool_round_id: str,
    *,
    timeout: int = 10,
    force_refresh: bool = False
) -> str:
    """
    Fetch pool results JSON with caching.

    Args:
        event_id: Event UUID
        pool_round_id: Pool round UUID
        timeout: Request timeout
        force_refresh: Bypass cache and force fresh fetch

    Returns:
        Raw JSON text

    Raises:
        FTLHTTPError: If fetch fails
    """
    path = f"/pools/results/data/{event_id}/{pool_round_id}"
    url = _build_url(path)
    cache_key = f"pool_results:{event_id}:{pool_round_id}"

    if not force_refresh:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    json_text = _fetch_with_retry(url, timeout=timeout)
    _cache.set(cache_key, json_text)
    return json_text


def fetch_tableau_raw(
    event_id: str,
    round_id: str,
    *,
    timeout: int = 10,
    force_refresh: bool = False
) -> str:
    """
    Fetch DE tableau HTML with caching.

    Args:
        event_id: Event UUID
        round_id: DE round UUID
        timeout: Request timeout
        force_refresh: Bypass cache and force fresh fetch

    Returns:
        Raw HTML text

    Raises:
        FTLHTTPError: If fetch fails
    """
    path = f"/tableaus/scores/{event_id}/{round_id}"
    url = _build_url(path)
    cache_key = f"tableau:{event_id}:{round_id}"

    if not force_refresh:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    html = _fetch_with_retry(url, timeout=timeout)
    _cache.set(cache_key, html)
    return html


def fetch_pools_bundle(
    event_id: str,
    pool_round_id: str,
    *,
    force_refresh: bool = False,
    timeout: int = 10,
    max_workers: int = 8
) -> dict:
    """
    Fetch complete pool data bundle: pool IDs, all pool HTML pages, and pool results.

    This is the main orchestrator function that:
    1. Fetches pool IDs list
    2. Fetches all individual pool HTML pages in parallel
    3. Fetches pool results JSON
    4. Parses all responses and returns structured data

    Args:
        event_id: Event UUID
        pool_round_id: Pool round UUID
        force_refresh: Bypass cache and force fresh fetch for all requests
        timeout: Request timeout in seconds
        max_workers: Maximum concurrent fetches (default: 8)

    Returns:
        dict with keys:
            - event_id: str
            - pool_round_id: str
            - pool_ids: list[str]
            - pools: list[dict] (each matches PoolDetails schema)
            - results: dict (matches PoolResults schema)

    Raises:
        FTLHTTPError: If any fetch fails
        FTLParseError: If any parse fails
    """
    # Step 1: Fetch and parse pool IDs
    try:
        pool_ids_html = fetch_pool_ids_raw(
            event_id,
            pool_round_id,
            timeout=timeout,
            force_refresh=force_refresh
        )
        pool_ids_data = parse_pool_ids(pool_ids_html)
        pool_ids = pool_ids_data["pool_ids"]
    except ValueError as e:
        raise FTLParseError(f"Failed to parse pool IDs: {e}") from e
    except Exception as e:
        raise FTLHTTPError(f"Failed to fetch pool IDs: {e}") from e

    if not pool_ids:
        raise FTLParseError("No pool IDs found")

    # Step 2: Fetch and parse all pool HTML pages in parallel
    pools = []
    failed_pools = []

    def fetch_and_parse_pool(pool_id: str) -> tuple[str, Optional[dict], Optional[Exception]]:
        """Fetch and parse a single pool. Returns (pool_id, parsed_data, error)."""
        try:
            html = fetch_pool_html_raw(
                event_id,
                pool_round_id,
                pool_id,
                timeout=timeout,
                force_refresh=force_refresh
            )
            parsed = parse_pool_html(html, pool_id=pool_id)
            return (pool_id, parsed, None)
        except Exception as e:
            return (pool_id, None, e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_and_parse_pool, pid): pid
            for pid in pool_ids
        }

        for future in as_completed(futures):
            pool_id, parsed, error = future.result()
            if error:
                failed_pools.append((pool_id, error))
            else:
                pools.append(parsed)

    if failed_pools:
        # Fail-fast: report which pools failed
        failures_str = "; ".join([
            f"{pid}: {str(err)}" for pid, err in failed_pools
        ])
        raise FTLHTTPError(f"Failed to fetch/parse {len(failed_pools)} pool(s): {failures_str}")

    # Sort pools by pool_number for consistent ordering
    pools.sort(key=lambda p: p.get("pool_number", 0))

    # Step 3: Fetch and parse pool results JSON
    try:
        results_json = fetch_pool_results_raw(
            event_id,
            pool_round_id,
            timeout=timeout,
            force_refresh=force_refresh
        )
        results_data = parse_pool_results(
            results_json,
            event_id=event_id,
            pool_round_id=pool_round_id
        )
    except ValueError as e:
        raise FTLParseError(f"Failed to parse pool results: {e}") from e
    except Exception as e:
        raise FTLHTTPError(f"Failed to fetch pool results: {e}") from e

    return {
        "event_id": event_id,
        "pool_round_id": pool_round_id,
        "pool_ids": pool_ids,
        "pools": pools,
        "results": results_data
    }


def clear_cache() -> None:
    """Clear all cached data. Useful for testing."""
    _cache.clear()
