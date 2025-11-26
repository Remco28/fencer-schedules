# Task: FTL Day 4 — HTTP Client, Bulk Pool Fetch, and In-Memory Cache Stub
**Date:** 2025-11-26  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Build a resilient HTTP client and bulk fetching pipeline to retrieve pool IDs, pool HTML, and pool results JSON for an event/round, using our existing parsers. Provide a minimal in-memory cache to reduce redundant fetches during development. No database writes yet.

## Scope (In)
- HTTP client module under `app/ftl/client.py` (or new file if preferred) with:
  - Configurable timeouts (default 10s)
  - Retry logic (3 attempts, exponential backoff base 0.5s, jitter optional)
  - Simple rate limiting/concurrency cap (ThreadPoolExecutor; default max 8–10 workers)
  - Clear exception types for HTTP failures and parse failures
- Bulk fetch function to:
  - Fetch pool IDs for a given event/pool round
  - Fetch pool HTML pages for each pool ID
  - Fetch pool results JSON for advancement status
  - Return structured dict ready for higher layers: `{"event_id": ..., "pool_round_id": ..., "pools": [...], "results": ...}`
- In-memory cache stub:
  - Keyed by full URL (or tuple of endpoint params)
  - TTL configurable (default 180 seconds)
  - Opt-in bypass flag to force refresh
- Integration wiring:
  - Use existing parsers: `parse_pool_ids`, `parse_pool_html`, `parse_pool_results`
  - Keep pure Python/requests (no new deps beyond `requests`, `bs4`, `pydantic`)
- Tests for the client/bulk logic using monkeypatched HTTP responses (no real network).

## Scope (Out)
- No database persistence
- No API routes
- No frontend changes
- No Redis or production-grade caching
- No DE tableau fetching (future task)

## Deliverables
1. Enhanced HTTP client utilities (timeout/retry) in `app/ftl/client.py` (or new helper module).
2. Bulk fetch orchestrator in `app/ftl/client.py` (or `app/ftl/service.py`) exposing:
   ```python
   def fetch_pools_bundle(event_id: str, pool_round_id: str, *, force_refresh: bool = False) -> dict:
       """
       Returns {
         "event_id": str,
         "pool_round_id": str,
         "pool_ids": [str],
         "pools": list[PoolDetails-compatible dict],
         "results": PoolResults-compatible dict
       }
       """
   ```
3. In-memory cache with TTL and bypass flag, used by fetch functions.
4. Unit tests in `tests/ftl/test_client_bulk_fetch.py` (or similar) that:
   - Mock HTTP responses for pool IDs, pool HTML (multiple pools), pool results
   - Validate retry on transient failure and respect concurrency cap
   - Validate cache hits vs. force refresh
   - Assert outputs pass pydantic validation for PoolDetails/PoolResults if possible
5. Documentation/log updates noting the new capabilities.

## Endpoints to cover
- Pool IDs: `/pools/scores/{eventID}` (HTML; use existing parse_pool_ids)
- Pool HTML: `/pools/scores/{eventID}/{roundID}/{poolID}?dbut=true` (HTML; use parse_pool_html)
- Pool Results JSON: `/pools/results/data/{eventID}/{roundID}` (JSON; use parse_pool_results)

## Requirements & Behavior
- Timeouts: default 10s; configurable per-call.
- Retries: 3 attempts on network errors or 5xx; no retry on 4xx.
- Concurrency: ThreadPoolExecutor with configurable max_workers (default 8–10). Avoid overwhelming FTL.
- Error handling:
  - If a pool fetch fails after retries, surface which pool_id failed.
  - If parsing fails, include pool_id or endpoint info in the exception.
  - Allow caller to decide whether to fail-fast or return partials; for this task, fail-fast with clear error.
- Caching:
  - Simple dict-based cache with timestamps.
  - Cache pool IDs, individual pool HTML responses, and pool results JSON responses.
  - TTL default 180s; force_refresh bypasses cache and overwrites entries.
- Parsing integration:
  - After fetch, run parsers; include `pool_id` in PoolDetails output.
  - For results, pass `event_id` and `pool_round_id` to `parse_pool_results`.
- Testing:
  - Use monkeypatch/fixtures to simulate HTTP responses; do not hit network.
  - Cover: successful end-to-end bundle, retry on first failure then success, cache hit path, force_refresh path, and parse failure reporting.
- Logging/print: avoid noisy logging; raise exceptions with clear messages instead.

## Acceptance Criteria
- Bulk fetch returns a dict with pool IDs, parsed pool details (matching PoolDetails schema), and parsed pool results (matching PoolResults schema).
- Cache reduces duplicate fetches within TTL and honors force_refresh.
- Retries and timeouts implemented; no unbounded concurrency.
- Tests added and passing: `.venv/bin/pytest tests/ftl`.
- Existing tests remain green.
