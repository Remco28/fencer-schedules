# Task: Restore Legacy Detail Views (Phase N)

**Goal:** Restore the missing "Pools Overview" and "DE Tableau" pages to fix broken links on the Tournament Detail page.

**Context:**
The "Tournament Detail" page links to `/pools` and `/de` for deep-dive views of specific events. However, these routes and their templates are currently missing from the codebase, causing 404 errors. The backend logic (helper functions) and CSS styling already exist.

**Branch:** `fix/restore-legacy-views`

---

## 1. Backend Changes (`app/main.py`)

Add the following route handlers. They should utilize the existing helper functions which already handle FTL fetching and smart caching.

### A. Pools Route
- **Path:** `/pools`
- **Method:** `GET`
- **Params:**
    - `event_id` (str, required)
    - `pool_round_id` (str, required)
    - `force_refresh` (bool, default False)
- **Logic:**
    1. Call `_do_pools_overview(event_id, pool_round_id, force_refresh)`.
    2. Render `pools.html`.
- **Context for Template:** `{"user": user, "data": data}` (where `data` is the return value of the helper).

### B. DE Route
- **Path:** `/de`
- **Method:** `GET`
- **Params:**
    - `event_id` (str, required)
    - `round_id` (str, required) - Note: this corresponds to `de_round_id`
    - `force_refresh` (bool, default False)
- **Logic:**
    1. Call `_do_de_tableau(event_id, round_id, force_refresh)`.
    2. Render `de.html`.
- **Context for Template:** `{"user": user, "data": data}`.

---

## 2. Frontend Changes (`app/templates/`)

Create two new template files. Use the existing CSS classes found in `app/static/styles.css` (e.g., `.pool-grid`, `.pool-card`, `.de-match`).

### A. `app/templates/pools.html`
**Structure:**
- Extend `base.html`.
- Header: "Pools Overview" + Refresh button.
- Content:
    - Loop through `data.pools`.
    - Container: `<div class="pool-grid">`
    - Item: `<article class="pool-card">`
        - Header: Pool Number + Strip (`.pool-header`, `.pool-strip`).
        - Roster: `<ul class="pool-roster">`
            - Fencer: `<li class="pool-fencer">`
                - Name/Club (`.pool-fencer-info`, `.pool-fencer-name`, `.pool-fencer-club`).
                - Status (`.status-advanced`, `.status-eliminated`, etc.).

### B. `app/templates/de.html`
**Structure:**
- Extend `base.html`.
- Header: "Elimination Bracket" + Refresh button.
- Content:
    - Loop through `data.groups` (which groups matches by round, e.g., "Table of 64").
    - Section: `<section class="de-round">`
        - Title: `<h3>{{ group.label }}</h3>`
        - Grid: `<div class="de-matches">`
            - Match: `<div class="de-match">`
                - Loop through competitors (2 per match).
                - Row: `<div class="de-competitor {{ 'winner' if is_winner }}">`
                    - Seed, Name, Club, Score (`.de-seed`, `.de-name`, `.de-club`, `.de-score`).

---

## 3. Verification

1.  **Start App:** Run the server.
2.  **Navigate:** Go to a Tournament Detail page (e.g., Capital Clash).
3.  **Click "Pools":** Verify it loads the grid of pools with fencers and statuses.
4.  **Click "DE":** Verify it loads the bracket matches.
5.  **Refresh:** Verify the refresh button works (appends `?force_refresh=true`).
