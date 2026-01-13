# Task: Day 9 — Basic Frontend: Pool Overview Page
**Date:** 2026-01-09
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective
Add a server-rendered “Pool Overview” page that lets an authenticated user enter an event ID and pool round ID and view all pools, fencers, and strip assignments. This page answers “Where are the pools and who is in them?” using the existing pools bundle API.

## User Stories
- As a logged-in user, I can enter an event ID and pool round ID to see all pools in that round.
- As a user, I can see each pool’s strip assignment and roster of fencers.
- As a user, I see clear errors if the request fails or inputs are invalid.

## Scope (In)
- New page: `/pools` (server-rendered HTML, requires auth).
- Form inputs: `event_id`, `pool_round_id`.
- Server-side handler that calls the existing pools bundle logic (no JS required).
- Render list/grid of pools with: pool number, strip assignment, fencer list (name + club), and per-fencer status when available.
- Error states and “no pools found” state.

## Scope (Out)
- Live auto-refresh.
- Pool bout matrix visualization.
- DE tableau UI.
- Persisted search history.

## Deliverables
1. **Route + Handler**
   - `GET /pools` renders form (auth required).
   - `POST /pools` submits form, calls pool bundle fetch, and renders results.
2. **Template**
   - `app/templates/pools.html` (extends `base.html`).
   - Pool list layout with headers for pool number/strip and fencer roster.
3. **Integration**
   - Reuse `fetch_pools_bundle` directly (same as API) or a small helper function in `app/main.py`.
   - Merge results so each fencer can display a status when present in pool results:
     - If a fencer appears in pool results, show `advanced`, `eliminated`, or `unknown`.
     - If missing, display `unknown`.
4. **Tests**
   - Add tests in `tests/web/test_pools.py`.
   - Use monkeypatch to avoid real HTTP.

## Implementation Notes
- **Auth:** `GET /pools` and `POST /pools` require `get_current_user`.
- **Form handling:** On POST, validate non-empty IDs and 32-char hex format.
- **Data source:** Use existing `fetch_pools_bundle(event_id, pool_round_id, force_refresh=False)`.
- **Normalization:**
  - Pools come from `parse_pool_html` with fencers and `pool_number`.
  - Results come from `parse_pool_results` list; map by fencer `name` (case-insensitive match).
  - If multiple name matches, prefer exact case match; otherwise first match.
- **Error handling:** Map `FTLHTTPError` (timeout vs connection), `FTLParseError`, and `ValueError` to user-friendly messages.
- **No results:** If pools list is empty, render a “No pools found” message.
- **Styling:** Extend `app/static/styles.css` with a pool card layout and status badges consistent with `/search`.

## Template Data Contract (example)
Pass a context like:
```
{
  "event_id": "...",
  "pool_round_id": "...",
  "pools": [
    {
      "pool_number": 1,
      "strip": "A5",
      "fencers": [
        {"name": "Jane Doe", "club": "XYZ", "status": "advanced"},
        {"name": "Sam Smith", "club": "ABC", "status": "unknown"}
      ]
    }
  ],
  "error": null
}
```

## Acceptance Criteria
- `/pools` renders for authenticated users and blocks unauthenticated access.
- Submitting valid IDs renders a list of pools with strip + roster.
- Status badges appear when results are available.
- Errors and empty states render cleanly.
- No regressions to `/api/*` endpoints or existing tests.
