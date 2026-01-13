# Task: Day 10 — Basic Frontend: Advancement Status Page
**Date:** 2026-01-14
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective
Add a server-rendered “Advancement Status” page that lets an authenticated user enter an event ID and pool round ID and view who advanced, who was eliminated, and who is unknown. This page answers “Who made the cut?” using the existing pool results data.

## User Stories
- As a logged-in user, I can enter an event ID and pool round ID to see advancement status for all fencers.
- As a user, I can filter or visually separate advanced, eliminated, and unknown statuses.
- As a user, I see clear errors if the request fails or inputs are invalid.

## Scope (In)
- New page: `/advancement` (server-rendered HTML, requires auth).
- Form inputs: `event_id`, `pool_round_id`.
- Server-side handler that fetches pool results (no JS required).
- Render grouped lists or sections: Advanced, Eliminated, Unknown.
- Error states and “no results found” state.

## Scope (Out)
- Live auto-refresh.
- Pool bout matrix visualization.
- DE tableau UI.
- Persisted search history.

## Deliverables
1. **Route + Handler**
   - `GET /advancement` renders form (auth required).
   - `POST /advancement` submits form, calls results fetch, and renders results.
2. **Template**
   - `app/templates/advancement.html` (extends `base.html`).
   - Three sections for statuses with counts and sorted fencer names.
3. **Integration**
   - Use `fetch_pools_bundle(event_id, pool_round_id)` and read `results.fencers`.
   - Normalize status to `advanced`, `eliminated`, `unknown` (fallback to `unknown`).
   - Sort each list by `place` (if available), then name.
4. **Tests**
   - Add tests in `tests/web/test_advancement.py`.
   - Use monkeypatch to avoid real HTTP.

## Implementation Notes
- **Auth:** `GET /advancement` and `POST /advancement` require `get_current_user`.
- **Form handling:** On POST, validate non-empty IDs and 32-char hex format.
- **Data source:** Use `fetch_pools_bundle(event_id, pool_round_id, force_refresh=False)` and read `bundle["results"]["fencers"]`.
- **Grouping:**
  - `status == "advanced"` → Advanced
  - `status == "eliminated"` → Eliminated
  - Anything else or missing → Unknown
- **Counts:** Display counts per group and total.
- **Error handling:** Map `FTLHTTPError` (timeout vs connection), `FTLParseError`, and `ValueError` to user-friendly messages.
- **No results:** If results list empty, render a “No results found” message.
- **Styling:** Reuse existing status badge classes and add small section headers if needed.

## Template Data Contract (example)
Pass a context like:
```
{
  "event_id": "...",
  "pool_round_id": "...",
  "groups": {
    "advanced": [{"name": "Jane Doe", "club": "XYZ", "place": 12}],
    "eliminated": [{"name": "Sam Smith", "club": "ABC", "place": 47}],
    "unknown": [{"name": "Lee Park", "club": "DEF", "place": null}]
  },
  "counts": {"advanced": 24, "eliminated": 18, "unknown": 3, "total": 45},
  "error": null
}
```

## Acceptance Criteria
- `/advancement` renders for authenticated users and blocks unauthenticated access.
- Submitting valid IDs renders grouped lists with counts.
- Status badges appear consistently with existing UI.
- Errors and empty states render cleanly.
- No regressions to `/api/*` endpoints or existing tests.
