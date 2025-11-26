# Task: FTL Day 3 — Pool Results JSON Parser (Advancement Status)
**Date:** 2025-11-26  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Parse the FencingTimeLive pool results JSON (`/pools/results/data/{eventID}/{roundID}`) to produce normalized advancement status for every fencer in a completed pool round. This feeds “Who advanced?” and “Who was eliminated?” views, and informs DE tableau lookups.

## Inputs
- Raw JSON from `GET /pools/results/data/{eventID}/{roundID}` (array of fencer result objects; see `docs/ftl-api-specification.md` §3).
- Fixture: Save a representative JSON sample to `comms/ftl_research_human_pools_results.md` (if not already present) for offline testing. Use real data from the November NAC sample where possible; otherwise construct a faithful sample with at least 6 fencers (mix of Advanced/Eliminated, include a tie=true case).

## Deliverables
1. New parser in `app/ftl/parsers/pool_results.py` with a public `parse_pool_results` function.
2. Pydantic schemas updated in `app/ftl/schemas.py` for pool results (see Contract).
3. Unit tests in `tests/ftl/test_pool_results_parser.py` covering happy path and edge cases using the fixture.
4. Documentation updates (log, next steps) noting the new parser.

## Contract (data model)
Add schemas:
- `PoolResult` fields (all ASCII):
  - `fencer_id: str` (source `id`)
  - `name: str`
  - `club_primary: str | None` (source `club1`)
  - `club_secondary: str | None` (source `club2`)
  - `division: str | None` (source `div`)
  - `country: str | None` (source `country`)
  - `place: int | None`
  - `victories: int` (source `v`)
  - `matches: int` (source `m`)
  - `victory_ratio: float | None` (source `vm`)
  - `touches_scored: int | None` (source `ts`)
  - `touches_received: int | None` (source `tr`)
  - `indicator: int | None` (source `ind`)
  - `prediction_raw: str | None` (source `prediction`)
  - `status: str` — one of `advanced`, `eliminated`, `unknown` (normalized from `prediction_raw`, case-insensitive; `"Advanced"` → `advanced`, anything else non-empty → `eliminated`, missing/empty → `unknown`)
  - `tie: bool | None` (source `tie`)
- `PoolResults` fields:
  - `event_id: str | None` (if caller passes)
  - `pool_round_id: str | None` (if caller passes)
  - `fencers: list[PoolResult]`

Parser signature:
```python
def parse_pool_results(raw: str | list[dict], *, event_id: str | None = None, pool_round_id: str | None = None) -> dict:
    """
    Returns dict matching PoolResults.
    """
```
- Accept either raw JSON string or already-loaded list of dicts.
- Preserve input order (FTL returns sorted by placement).
- Raise `ValueError` on invalid JSON, non-list payloads, or empty arrays.
- Raise `ValueError` if required fields (`id`, `name`, `v`, `m`, `prediction` optional but `status` must be derivable) are missing.
- Normalize missing optional numeric fields to `None` instead of failing.

## Implementation notes
- Place parser in `app/ftl/parsers/pool_results.py` and import it in `app/ftl/parsers/__init__.py` if you want easier access.
- Keep pure parsing: no I/O, no HTTP, no DB writes, no caching.
- Normalize strings with `strip()`; leave names/clubs/country casing as provided by FTL.
- Convert `indicator` to int if present; otherwise `None`.
- `status` derivation:
  - If `prediction_raw` (case-insensitive) == `"advanced"` → `advanced`
  - Else if `prediction_raw` truthy → `eliminated`
  - Else → `unknown`
- Do not filter out eliminated fencers; include full list.
- Ensure compatibility with existing `.venv` deps (pydantic already present).

## Testing requirements (`tests/ftl/test_pool_results_parser.py`)
- Happy path: parse the saved fixture; assert length, ordering, and representative field values (e.g., first entry status `advanced`, another with `eliminated`, tie flag preserved).
- Status mapping: `"Advanced"` → `advanced`; another non-empty string (e.g., `"Eliminated"` or `"Cut"`) → `eliminated`; missing/empty → `unknown`.
- Numeric parsing: `victory_ratio` as float, `indicator` as int; missing optional fields become `None`.
- Error cases:
  - Invalid JSON string raises `ValueError`.
  - Non-list top-level (e.g., `{}`) raises `ValueError`.
  - Empty list raises `ValueError`.
  - Missing required fields (`id`, `name`, `v`, `m`) raises `ValueError`.
- Order preservation: ensure parsed list order matches input order (placement ascending).

## Out of scope
- HTTP client/fetching, retries, or parallelism.
- Database writes or caching.
- API/route wiring.
- DE tableau parsing (separate task).

## Acceptance criteria
- New schemas and parser implemented per contract above.
- Tests in `tests/ftl/test_pool_results_parser.py` pass and run via `.venv/bin/pytest tests/ftl`.
- Existing tests (`tests/ftl/test_pool_ids.py`, `tests/ftl/test_pools_parser.py`) remain green.
- Fixture saved at `comms/ftl_research_human_pools_results.md` and used by tests.
