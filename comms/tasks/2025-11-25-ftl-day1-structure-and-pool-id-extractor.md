# Task: FTL Day 1 — Project Structure + Pool ID Extractor
**Owner:** ARCHITECT  
**Role:** Developer (implementer)  
**Status:** SPEC READY  
**Date:** 2025-11-25

## Objective
Lay the foundation for FencingTimeLive (FTL) live tracking in the existing `project_kickstart` codebase and deliver the first parser (pool ID extractor). This app is **mobile-first** and **read-only**—no email notifications or digests.

## Deliverables
1) **FTL module scaffold** under `project_kickstart/app/ftl/` with clear boundaries.  
2) **Schema additions** for FTL linkage (event and round IDs) stored in SQLite alongside existing tables.  
3) **Pool ID extractor** that parses the FTL event page HTML/JS and returns pool round ID + individual pool IDs.  
4) **Tests** covering the extractor using the provided sample artifact.

## Scope & Constraints
- Keep existing registration/email features untouched; do not add email/push.  
- Stay synchronous (`requests`/`bs4`) for now; concurrency/caching will come later.  
- Keep the UI untouched for this task—API and parser only.  
- SQLite is fine; migrations can be simple `Base.metadata.create_all` for now (no Alembic changes required today).

## Implementation Details

### 1) Module layout
- Create `project_kickstart/app/ftl/` with:
  - `__init__.py`
  - `models.py` (SQLAlchemy models for FTL linkage/caching)
  - `client.py` (HTTP fetch wrapper; stub OK for now)
  - `parsers/__init__.py`
  - `parsers/pool_ids.py` (pool ID extractor implementation)
  - `schemas.py` (Pydantic response shapes for API/use)

### 2) Database models (extend existing Base)
Add to `app/ftl/models.py` (import `Base` from `app.models`):
- `FTLEventLink`  
  - `id` (PK)  
  - `event_id` (str, required) — FTL event UUID  
  - `pool_round_id` (str, required) — round UUID for pools  
  - `de_round_id` (str, nullable) — round UUID for tableau when known  
  - `source_url` (str, required) — user-provided FTL URL  
  - `label` (str, optional) — friendly name for the event  
  - `created_at`, `updated_at` (DateTime, utcnow defaults)  
  - Unique constraint on `event_id`
- `FTLPoolsSnapshot` (lightweight cache of pool ID listing)  
  - `id` (PK)  
  - `event_id` (str, FK not necessary)  
  - `pool_round_id` (str)  
  - `pool_ids` (JSON/text) — serialized list of pool IDs  
  - `fetched_at` (DateTime, required)  
  - Composite index `(event_id, pool_round_id)`

Hook: ensure `app.main.init_db()` will pick these up (import `app.ftl.models` inside `app/main.py` or `app/database.py` before `Base.metadata.create_all` runs).

### 3) Pool ID extractor (`parsers/pool_ids.py`)
Function signature:
```python
def parse_pool_ids(html: str) -> dict:
    """
    Returns {"pool_round_id": "<uuid>", "pool_ids": ["<uuid1>", "<uuid2>", ...]}
    Raises ValueError with a descriptive message when parsing fails.
    """
```
Behavior:
- Parse the event page HTML (string) and locate the JavaScript array/object that lists pool IDs and the pool round ID. The sample `comms/ftl_research_human_pool_ids.md` includes a JS array.
- Strip HTML/markdown wrappers as needed; be resilient to surrounding text.
- Normalize output: pool IDs as uppercase strings; deduplicate while preserving input order.
- Validate: error if no pool IDs found or pool round ID missing.

Implementation notes (from research):
- Pool round ID and pool IDs are embedded in a JS array like `var poolRounds = [...]` or similar; the sample contains `D6890CA440324D9E8D594D5682CC33B7` as the pool round ID for November NAC.
- Use `re` to extract the JSON-ish block, then `json.loads` after minor cleanup (replace single quotes, ensure valid JSON).
- Keep the parser pure/deterministic (no network, no file I/O).

### 4) Schemas
- In `schemas.py`, add Pydantic models:
  - `PoolIdListing` with fields `event_id: str | None = None`, `pool_round_id: str`, `pool_ids: list[str]`.

### 5) HTTP client (stub)
- In `client.py`, add a simple `fetch_html(url: str, timeout: int = 10) -> str` using `requests.get` with desktop UA, raising `ValueError` on non-2xx or empty body. This will be wired later to the parser and caching.

### 6) Tests
- Add tests under `project_kickstart/tests/ftl/test_pool_ids.py`.
- Load the sample string from `comms/ftl_research_human_pool_ids.md` (read file) and assert:
  - `pool_round_id == "D6890CA440324D9E8D594D5682CC33B7"` (from manifest)
  - `pool_ids` contains the known set from the sample (assert length > 1 and includes at least a couple of concrete IDs from the sample; keep the list explicit).
  - Deduplication works (feed a duplicated ID snippet and ensure output is unique, order preserved).
  - Raises `ValueError` on malformed input (missing array).

### 7) API wiring (minimal placeholder)
- No new routes required for this task; optional: add a placeholder module `app/api/ftl.py` with a TODO comment and router stub, but do not mount it yet.

## Acceptance Criteria
- New FTL module structure exists with the files above.
- `parse_pool_ids` returns expected `pool_round_id` and `pool_ids` for the provided sample; tests pass.
- New models are registered with SQLAlchemy Base and can be created via `init_db()` (no runtime import errors).
- No changes to existing auth/registration/email behavior.

## Out of Scope (for this task)
- Pool/DE HTML parsers, results JSON parser, caching layer, concurrency, APIs, or UI changes.
- Notifications (email/push) and digest scheduling.

## How to Run
- Tests: `cd project_kickstart && pytest tests/ftl/test_pool_ids.py`
- DB init (optional check): `cd project_kickstart && python -m app.main db_init` (should create new FTL tables).

## Notes for Implementer
- Keep code comments focused on non-obvious parsing steps.
- Use ASCII only.  
- If you add imports that require new dependencies, update `requirements.txt` (likely none needed beyond stdlib).  
- If you add router stubs, do not include them in `app.main` yet to avoid breaking routes until implemented.
