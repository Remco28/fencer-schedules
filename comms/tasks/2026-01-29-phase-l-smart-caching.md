# Task: Phase L — Smart Caching (Skip Completed Events)

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Drastically reduce dashboard load times by identifying completed events and caching their data for long periods, rather than re-fetching them on every dashboard load.

## Core Logic

1.  **Identify Completion:** When parsing an event, detect if it is "Finished" (e.g., Gold Medal awarded, or results exist and date is in past).
2.  **Flag Event:** Store this `is_completed` state in the `CachedEvent` database record.
3.  **Long-Term Cache:** When fetching data for a completed event, use a **Long TTL** (e.g., 24 hours) instead of the standard short TTL (3 minutes).

## Required Changes

### 1. Database Schema (`app/models.py`)

Update `CachedEvent`:
-   Add `is_completed = Column(Boolean, default=False)`
-   Add `completed_at = Column(DateTime, nullable=True)`

*Note: Update `init_db` or use a migration pattern if strictly required, but for this project, checking/creating the column on startup or advising a DB reset is acceptable.*

### 2. Service Logic (`app/services/tournament_service.py`)

**A. Detect Completion:**
In `get_tournament_fencer_status` or a helper:
-   After fetching/parsing, check the data:
    -   **Pools:** All bouts finished? (Hard to know for sure).
    -   **DEs:** Is there a "Final" match with a status of "Complete"? OR does the "Results" endpoint return a full list?
-   If detected as complete:
    -   Update `event.is_completed = True`.
    -   Commit to DB.

**B. Smart Fetching:**
Update the fetch calls inside `get_tournament_fencer_status`:
-   Check `event.is_completed`.
-   If `True`:
    -   Call `fetch_pools_bundle` / `fetch_tableau_raw` / `fetch_event_results_json` with a **special flag** or `ttl` parameter (need to update client).
    -   OR, simply rely on the fact that if we don't pass `force_refresh=True`, the cache *could* hold it longer?
    -   **Better Approach:** Update `app/ftl/client.py` to accept a custom `ttl` override.

### 3. Client Update (`app/ftl/client.py`)

Update `_fetch_with_retry` and the cache wrappers:
-   Allow passing a `ttl` argument to the fetch functions.
-   If `ttl` is provided, use it for `_cache.set()`.
-   Default remains 180s.

**Usage in Service:**
```python
# In tournament_service.py
ttl = 86400 if event.is_completed else 180 # 24 hours vs 3 minutes
data = fetch_pools_bundle(..., ttl=ttl)
```

## Acceptance Criteria

- [ ] `CachedEvent` model has `is_completed` field.
- [ ] Events are correctly marked as completed when the Final bout is done.
- [ ] Fetches for completed events use a long TTL (verify logs or cache behavior).
- [ ] Dashboard loads significantly faster on subsequent refreshes for old tournaments.
