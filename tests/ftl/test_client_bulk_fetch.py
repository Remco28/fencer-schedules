"""Tests for FTL HTTP client and bulk fetch orchestration."""
import os
import re
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, RequestException

from app.ftl.client import (
    FTLHTTPError,
    FTLParseError,
    SimpleCache,
    _fetch_with_retry,
    fetch_pool_ids_raw,
    fetch_pool_html_raw,
    fetch_pool_results_raw,
    fetch_pools_bundle,
    clear_cache,
)


# Paths to sample fixtures
POOL_IDS_SAMPLE = os.path.join(
    os.path.dirname(__file__), "..", "..", "comms", "ftl_research_human_pool_ids.md"
)
POOL_HTML_SAMPLE = os.path.join(
    os.path.dirname(__file__), "..", "..", "comms", "ftl_research_human_pools.md"
)
POOL_RESULTS_SAMPLE = os.path.join(
    os.path.dirname(__file__), "..", "..", "comms", "ftl_research_human_pools_results.md"
)


def load_pool_ids_html():
    """Load pool IDs HTML sample."""
    with open(POOL_IDS_SAMPLE, 'r', encoding='utf-8') as f:
        content = f.read()
    html_match = re.search(r'```html\n(.*?)\n```', content, re.DOTALL)
    if not html_match:
        raise ValueError("Could not extract HTML")
    return html_match.group(1)


def load_pool_html():
    """Load pool HTML sample."""
    with open(POOL_HTML_SAMPLE, 'r', encoding='utf-8') as f:
        content = f.read()
    html_match = re.search(r'```html\n(.*?)\n```', content, re.DOTALL)
    if not html_match:
        raise ValueError("Could not extract HTML")
    return html_match.group(1)


def load_pool_results_json():
    """Load pool results JSON sample."""
    with open(POOL_RESULTS_SAMPLE, 'r', encoding='utf-8') as f:
        content = f.read()
    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
    if not json_match:
        raise ValueError("Could not extract JSON")
    return json_match.group(1)


class TestSimpleCache:
    """Tests for SimpleCache class."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get."""
        cache = SimpleCache(default_ttl=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        cache = SimpleCache()
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        """Test that cached values expire after TTL."""
        cache = SimpleCache(default_ttl=1)
        cache.set("key1", "value1", ttl=1)

        # Should be present immediately
        assert cache.get("key1") == "value1"

        # Wait for expiry
        time.sleep(1.1)

        # Should be expired
        assert cache.get("key1") is None

    def test_cache_clear(self):
        """Test cache clear."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_custom_ttl(self):
        """Test cache with custom TTL overriding default."""
        cache = SimpleCache(default_ttl=10)
        cache.set("key1", "value1", ttl=1)

        # Should exist
        assert cache.get("key1") == "value1"

        # Wait for custom TTL to expire
        time.sleep(1.1)

        # Should be gone
        assert cache.get("key1") is None


class TestFetchWithRetry:
    """Tests for _fetch_with_retry function."""

    def test_successful_fetch_first_attempt(self):
        """Test successful fetch on first attempt."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "test content"
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            result = _fetch_with_retry("http://test.com")
            assert result == "test content"

    def test_retry_on_timeout(self):
        """Test retry on timeout error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "success"
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get') as mock_get:
            # First call times out, second succeeds
            mock_get.side_effect = [Timeout(), mock_response]

            with patch('app.ftl.client.time.sleep'):  # Skip actual sleep
                result = _fetch_with_retry("http://test.com", max_retries=3)
                assert result == "success"
                assert mock_get.call_count == 2

    def test_retry_exhausted_raises_error(self):
        """Test that FTLHTTPError is raised after max retries."""
        with patch('app.ftl.client.requests.get', side_effect=Timeout()):
            with patch('app.ftl.client.time.sleep'):
                with pytest.raises(FTLHTTPError, match="Failed to fetch URL after 3 attempts"):
                    _fetch_with_retry("http://test.com", max_retries=3)

    def test_no_retry_on_4xx_errors(self):
        """Test that 4xx errors don't trigger retries."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            with pytest.raises(FTLHTTPError, match="HTTP 404"):
                _fetch_with_retry("http://test.com")

    def test_retry_on_5xx_errors(self):
        """Test retry on 5xx server errors."""
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.raise_for_status = Mock(side_effect=RequestException())

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.text = "success"
        mock_response_200.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get') as mock_get:
            mock_get.side_effect = [mock_response_500, mock_response_200]

            with patch('app.ftl.client.time.sleep'):
                result = _fetch_with_retry("http://test.com", max_retries=3)
                assert result == "success"
                assert mock_get.call_count == 2

    def test_empty_response_raises_error(self):
        """Test that empty response raises error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            with pytest.raises(FTLHTTPError, match="Empty response"):
                _fetch_with_retry("http://test.com")


class TestFetchRawFunctions:
    """Tests for fetch_*_raw functions with caching."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_fetch_pool_ids_raw_success(self):
        """Test successful pool IDs fetch."""
        html_content = load_pool_ids_html()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            result = fetch_pool_ids_raw("event123", "round456")
            assert "var ids" in result
            assert len(result) > 0

    def test_fetch_pool_ids_caching(self):
        """Test that pool IDs are cached."""
        html_content = load_pool_ids_html()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response) as mock_get:
            # First call
            result1 = fetch_pool_ids_raw("event123", "round456")

            # Second call (should use cache)
            result2 = fetch_pool_ids_raw("event123", "round456")

            assert result1 == result2
            assert mock_get.call_count == 1  # Only one actual HTTP call

    def test_fetch_pool_ids_force_refresh(self):
        """Test force_refresh bypasses cache."""
        html_content = load_pool_ids_html()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response) as mock_get:
            # First call
            fetch_pool_ids_raw("event123", "round456")

            # Second call with force_refresh
            fetch_pool_ids_raw("event123", "round456", force_refresh=True)

            assert mock_get.call_count == 2  # Two HTTP calls

    def test_fetch_pool_html_raw_success(self):
        """Test successful pool HTML fetch."""
        html_content = load_pool_html()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            result = fetch_pool_html_raw("event123", "round456", "pool789")
            assert "poolNum" in result
            assert len(result) > 0

    def test_fetch_pool_results_raw_success(self):
        """Test successful pool results fetch."""
        json_content = load_pool_results_json()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json_content
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            result = fetch_pool_results_raw("event123", "round456")
            assert "IMREK Elijah S." in result or "GAO Daniel" in result
            assert len(result) > 0


class TestFetchPoolsBundle:
    """Tests for fetch_pools_bundle orchestrator."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_successful_bundle_fetch(self):
        """Test successful end-to-end bundle fetch."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        def mock_get_side_effect(url, *args, **kwargs):
            """Mock responses based on URL."""
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                # Pool results JSON (check this first, before pool scores)
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                # Individual pool HTML
                mock_response.text = pool_html
            elif "/pools/scores/" in url:
                # Pool IDs page (has 5 path segments: / pools / scores / event / round)
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown URL"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect):
            result = fetch_pools_bundle("event123", "round456", max_workers=2)

            # Validate structure
            assert "event_id" in result
            assert "pool_round_id" in result
            assert "pool_ids" in result
            assert "pools" in result
            assert "results" in result

            assert result["event_id"] == "event123"
            assert result["pool_round_id"] == "round456"

            # Pool IDs should be extracted (45 from our sample)
            assert len(result["pool_ids"]) == 45

            # Pools should be parsed (45 pools fetched)
            assert len(result["pools"]) == 45

            # Each pool should have required fields
            for pool in result["pools"]:
                assert "pool_id" in pool
                assert "pool_number" in pool
                assert "strip" in pool or pool["strip"] is None
                assert "fencers" in pool
                assert "bouts" in pool

            # Results should be parsed
            assert "fencers" in result["results"]
            assert len(result["results"]["fencers"]) == 6  # Our sample has 6

    def test_bundle_fetch_with_cache(self):
        """Test that bundle fetch uses cache on subsequent calls."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        def mock_get_side_effect(url, *args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                mock_response.text = pool_html
            elif "/pools/scores/" in url:
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect) as mock_get:
            # First call
            result1 = fetch_pools_bundle("event123", "round456", max_workers=2)

            # Second call (should use cache)
            result2 = fetch_pools_bundle("event123", "round456", max_workers=2)

            # Results should be identical
            assert result1["event_id"] == result2["event_id"]
            assert len(result1["pools"]) == len(result2["pools"])

            # Should have: 1 pool IDs fetch + 45 pool HTML fetches + 1 pool results fetch = 47
            # Second call should use cache, so still 47 total
            assert mock_get.call_count == 47

    def test_bundle_fetch_force_refresh(self):
        """Test force_refresh bypasses cache."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        def mock_get_side_effect(url, *args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                mock_response.text = pool_html
            elif "/pools/scores/" in url:
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect) as mock_get:
            # First call
            fetch_pools_bundle("event123", "round456", max_workers=2)

            # Second call with force_refresh
            fetch_pools_bundle("event123", "round456", force_refresh=True, max_workers=2)

            # Should have double the calls: 47 + 47 = 94
            assert mock_get.call_count == 94

    def test_bundle_fetch_parse_error(self):
        """Test that parse errors are reported as FTLParseError."""
        invalid_html = "<html><body>Invalid pool IDs page</body></html>"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = invalid_html
        mock_response.raise_for_status = Mock()

        with patch('app.ftl.client.requests.get', return_value=mock_response):
            with pytest.raises(FTLParseError, match="Failed to parse pool IDs"):
                fetch_pools_bundle("event123", "round456")

    def test_bundle_fetch_http_error(self):
        """Test that HTTP errors are reported as FTLHTTPError."""
        with patch('app.ftl.client.requests.get', side_effect=Timeout()):
            with patch('app.ftl.client.time.sleep'):
                with pytest.raises(FTLHTTPError, match="Failed to fetch"):
                    fetch_pools_bundle("event123", "round456")

    def test_bundle_fetch_partial_pool_failure(self):
        """Test that individual pool fetch failures are reported."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        def mock_get_side_effect(url, *args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                # Always fail pool fetches to trigger error
                raise Timeout()
            elif "/pools/scores/" in url:
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect):
            with patch('app.ftl.client.time.sleep'):
                with pytest.raises(FTLHTTPError, match="Failed to fetch/parse .* pool"):
                    fetch_pools_bundle("event123", "round456", max_workers=2)

    def test_bundle_fetch_validates_schema_compatibility(self):
        """Test that returned data is compatible with Pydantic schemas."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        def mock_get_side_effect(url, *args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                mock_response.text = pool_html
            elif "/pools/scores/" in url:
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect):
            result = fetch_pools_bundle("event123", "round456", max_workers=2)

            # Validate PoolDetails compatibility for each pool
            from app.ftl.schemas import PoolDetails, PoolResults

            for pool_data in result["pools"]:
                pool_obj = PoolDetails(**pool_data)
                assert pool_obj.pool_number is not None
                assert isinstance(pool_obj.fencers, list)
                assert isinstance(pool_obj.bouts, list)

            # Validate PoolResults compatibility
            results_obj = PoolResults(**result["results"])
            assert isinstance(results_obj.fencers, list)
            assert len(results_obj.fencers) > 0


class TestConcurrencyAndRateLimiting:
    """Tests for concurrency control."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_respects_max_workers(self):
        """Test that max_workers limits concurrent requests."""
        pool_ids_html = load_pool_ids_html()
        pool_html = load_pool_html()
        pool_results_json = load_pool_results_json()

        active_requests = [0]
        max_concurrent = [0]
        lock = MagicMock()

        def mock_get_side_effect(url, *args, **kwargs):
            active_requests[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_requests[0])

            # Simulate some processing time
            time.sleep(0.01)

            active_requests[0] -= 1

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            if "/pools/results/data/" in url:
                mock_response.text = pool_results_json
            elif "?dbut=true" in url:
                mock_response.text = pool_html
            elif "/pools/scores/" in url:
                mock_response.text = pool_ids_html
            else:
                mock_response.text = "Unknown"

            return mock_response

        with patch('app.ftl.client.requests.get', side_effect=mock_get_side_effect):
            # Use small max_workers to test limiting
            fetch_pools_bundle("event123", "round456", max_workers=3)

            # Should never exceed max_workers
            assert max_concurrent[0] <= 3
