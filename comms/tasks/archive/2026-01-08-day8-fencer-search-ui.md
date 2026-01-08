# Task: Day 8 — Basic Frontend: Fencer Search Page
**Date:** 2026-01-08  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Add a minimal, server-rendered fencer search UI that lets an authenticated user query the live FTL API and view results in a clean list. This is the first “basic frontend feature” and should work end-to-end using existing `/api/pools/{event_id}/{pool_round_id}/fencer` data.

## User Stories
- As a logged-in user, I can enter an event ID, pool round ID, and fencer name to search.
- As a logged-in user, I can view a results list showing pool strip and status when available.
- As a user, I see clear errors if the search fails or inputs are invalid.

## Scope (In)
- New page: `/search` (server-rendered HTML, requires auth).
- Form inputs: `event_id`, `pool_round_id`, `name`.
- Server-side handler that calls internal API to fetch results (no JS required).
- Results list with basic metadata (name, pool_number, strip, club, status/source).
- Error states and “no results” state.

## Scope (Out)
- Client-side SPA or live auto-refresh.
- DE tableau UI.
- Pool/strip visualization.
- Persistence of search history.

## Deliverables
1. **Route + Handler**
   - Add `GET /search` to render the form.
   - Add `POST /search` to submit form, call search, and render results.
2. **Template**
   - `app/templates/search.html` (extends `base.html`).
   - Form fields and results display.
3. **API Integration**
   - Reuse internal call to `search_fencer()` (Python function in `app/main.py`) instead of making external HTTP calls.
   - Map errors from the FTL client to user-friendly messages.
4. **Tests**
   - Add tests in `tests/web/test_search.py` (or extend `tests/web/test_auth.py`).
   - Use dependency overrides or monkeypatch to avoid real HTTP.

## Implementation Notes
- **Auth:** `GET /search` and `POST /search` require `get_current_user`.
- **Form handling:** On POST, read form values; validate simple non-empty + length (32 chars for IDs).
- **Calling API:** Import and call `search_fencer()` directly with `force_refresh=False`.
- **Results format:** Use the existing response shape:
  - `matches`: list of `{name, pool_number, strip, club, status, source, ...}`
- **Errors:** For missing/invalid inputs, render `search.html` with an inline error message.
- **No results:** Render a “No matches found” message.
- **Styling:** Use existing Pico CSS + `app/static/styles.css` classes where possible.

## Acceptance Criteria
- `/search` renders for authenticated users and redirects/401 for unauthenticated users.
- Submitting the form renders results using real API data.
- Errors and empty results are displayed cleanly.
- No regressions to `/api/*` endpoints or existing tests.

