# Task: Day 11 — Basic Frontend: DE Tableau Page
**Date:** 2026-01-14
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective
Add a server-rendered “DE Tableau” page that lets an authenticated user enter an event ID and DE round ID and view a readable elimination bracket listing. This page answers “Who is fencing whom in DE, and what are the results?” using the existing DE tableau parser.

## User Stories
- As a logged-in user, I can enter an event ID and DE round ID to see all DE matches.
- As a user, I can see round labels, fencers, scores, strip/time, and winner status.
- As a user, I see clear errors if the request fails or inputs are invalid.

## Scope (In)
- New page: `/de` (server-rendered HTML, requires auth).
- Form inputs: `event_id`, `round_id`.
- Server-side handler that fetches and parses tableau HTML (no JS required).
- Render a list grouped by round (e.g., Table of 64, 32, 16, QF, SF, F).
- Error states and “no matches found” state.

## Scope (Out)
- Visual bracket drawing (no SVG bracket).
- Live auto-refresh.
- Editing or annotations.
- Persisted search history.

## Deliverables
1. **Route + Handler**
   - `GET /de` renders form (auth required).
   - `POST /de` submits form, calls tableau fetch/parse, and renders results.
2. **Template**
   - `app/templates/de_tableau.html` (extends `base.html`).
   - Grouped sections by round with match rows.
3. **Integration**
   - Use `fetch_tableau_raw(event_id, round_id)` then `parse_de_tableau(...)`.
   - Normalize matches into round groups. Unknown round goes to “Other”.
   - Sort matches within a round by `path` if present, else by seed/name.
4. **Tests**
   - Add tests in `tests/web/test_de_tableau.py`.
   - Use monkeypatch to avoid real HTTP.

## Implementation Notes
- **Auth:** `GET /de` and `POST /de` require `get_current_user`.
- **Form handling:** On POST, validate non-empty IDs and 32-char hex format.
- **Data source:** Use `fetch_tableau_raw` and `parse_de_tableau` with `event_id` and `round_id`.
- **Grouping:**
  - Use `match["round"]` (e.g., "64", "32", "16", "QF", "SF", "F").
  - Provide human-friendly labels: "Table of 64", "Quarterfinal", etc.
- **Winner display:** If `winner` is "A" or "B", highlight the winner’s name.
- **Error handling:** Map `FTLHTTPError` (timeout vs connection), `FTLParseError`, and `ValueError` to user-friendly messages.
- **No results:** If matches list empty, render a “No matches found” message.
- **Styling:** Add minimal styling for match rows and winner highlight; reuse existing badge styles where appropriate.

## Template Data Contract (example)
Pass a context like:
```
{
  "event_id": "...",
  "round_id": "...",
  "groups": [
    {
      "label": "Table of 32",
      "matches": [
        {
          "name_a": "Jane Doe",
          "name_b": "Sam Smith",
          "seed_a": 3,
          "seed_b": 30,
          "score_a": 15,
          "score_b": 9,
          "winner": "A",
          "strip": "B7",
          "time": "2:15 PM"
        }
      ]
    }
  ],
  "error": null
}
```

## Acceptance Criteria
- `/de` renders for authenticated users and blocks unauthenticated access.
- Submitting valid IDs renders grouped match lists with round labels.
- Winner highlighting is visible when a winner exists.
- Errors and empty states render cleanly.
- No regressions to `/api/*` endpoints or existing tests.
