# Task: FTL Day 6 — API Endpoints & Data Integration
**Date:** 2025-11-26  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Expose the scraped FTL data via a minimal FastAPI service, wiring together existing parsers and the HTTP client. Provide endpoints to fetch pools, pool results, and DE tableau data for a given event/round, returning normalized JSON that matches our schemas. Include basic error handling and in-memory caching reuse.

## Scope (In)
- FastAPI app scaffold under `app/api/` (or `app/main.py` if simpler).
- Endpoints:
  1) `GET /api/pools/{event_id}/{pool_round_id}` → returns pool IDs + parsed pools + pool results.
  2) `GET /api/pools/{event_id}/{pool_round_id}/fencer` with query `name` (case-insensitive contains) → filters across pools/results to return matching fencer entries and pool location/strip if present.
  3) `GET /api/de/{event_id}/{de_round_id}` → returns parsed DE tableau.
- Use existing orchestration:
  - `fetch_pools_bundle` (uses parsers + caching)
  - `parse_de_tableau` fed by `fetch_html` (or a new fetch helper for tableau with retry/cache)
- Wire schemas for response validation: `PoolDetails`, `PoolResults`, `Tableau`.
- Lightweight in-memory cache reuse from `app/ftl/client.py` to avoid refetching during the same process.
- Basic configuration via env vars (timeout, max_workers, cache TTL) with sensible defaults.
- Unit tests for the API layer with TestClient + mocked HTTP (no real network).

## Scope (Out)
- Authentication/authorization.
- Persistent storage/Redis.
- Frontend/UI.
- CI/CD or deployment scripts.

## Deliverables
1. FastAPI app entry (e.g., `app/main.py`) and router(s) under `app/api/`.
2. Endpoint implementations:
   - Pools bundle: returns `{event_id, pool_round_id, pool_ids, pools, results}` (reuse output of `fetch_pools_bundle`).
   - Fencer search: query param `name`, returns array of matches with fencer info + pool metadata (pool_number, strip) and advancement status if available; case-insensitive substring match across pool fencers and pool results.
   - DE tableau: returns `{event_id, round_id, matches}` from `parse_de_tableau`.
3. HTTP fetch helper for tableau with retry/cache (e.g., `fetch_tableau_raw`), similar to existing raw fetchers.
4. Error handling: map `FTLHTTPError` → 502/504, `FTLParseError` → 500, bad input → 400. Include a concise `detail` message.
5. Tests in `tests/api/test_api.py` (or similar) using FastAPI TestClient and monkeypatched HTTP responses:
   - Happy paths for each endpoint.
   - Error mapping for HTTP/parse failures.
   - Fencer search matching multiple pools.
   - Cache reuse not strictly required to assert, but ensure no real HTTP calls.
6. Docs/log updates noting the new API layer and how to run it.

## API Contracts (Responses)
- `/api/pools/{event_id}/{pool_round_id}`: JSON structure identical to `fetch_pools_bundle` output.
- `/api/pools/{event_id}/{pool_round_id}/fencer?name=smith`: returns `{"query": "smith", "matches": [ { "name": ..., "pool_number": ..., "strip": ..., "club": ..., "status": ..., "source": "pool" | "results" } ]}`; include both pool roster matches and results matches; de-duplicate by name+pool_number.
- `/api/de/{event_id}/{de_round_id}`: JSON matching `Tableau` schema.

## Implementation Notes
- Keep API pure: no DB writes.
- Add small helper to normalize names for matching (lowercase, strip). For pool roster matches, status may be unknown; for results, include `status` from pool results parser when available.
- Reuse `fetch_pools_bundle` for both endpoints (pools and fencer search) to avoid double fetch; optionally allow `force_refresh` query param (bool) to bypass cache.
- Add `fetch_tableau_raw(event_id, round_id, ...)` mirroring other raw fetchers; cache with TTL.
- Configure FastAPI app so `uvicorn app.main:app` works.

## Testing Requirements
- Use TestClient with patched `requests.get` to serve fixture HTML/JSON (reuse existing fixtures).
- Pools endpoint: assert keys present, length of pools/ids, and that data matches fixtures.
- Fencer search: search “smith” should return pool roster match and pool results match if present; ensure case-insensitive.
- DE endpoint: returns matches and preserves round info from parser.
- Error mapping: simulate HTTP failure (Timeout) and parse failure to verify status codes and messages.

## Acceptance Criteria
- Endpoints implemented and validated with Pydantic responses.
- Tests in `tests/api/test_api.py` pass via `.venv/bin/pytest`.
- Existing tests remain green.
- Docs updated (log, manifest, next steps) to reflect new API layer.
