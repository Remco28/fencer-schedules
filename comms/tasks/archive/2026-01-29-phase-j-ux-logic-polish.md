# Task: Phase J — UX & Logic Polish

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Fix critical usability issues identified in testing: broken search input layout, strict name matching that frustrates users, incorrect "Waiting" status for finished events, and button misalignment.

## Required Changes

### 1. Fix Search UI Layout (`app/static/styles.css` & `app/templates/search.html`)

**Problem:** The search input box is compressed to a tiny width (Screenshot 6).
**Fix:**
-   In `.search-form`:
    -   Ensure the input container or the input itself has `flex: 1` (flex-grow).
    -   Set a `min-width: 200px` on the text input.
    -   Ensure the label is above or clearly separated.
-   Make the input height match the button height (use `height: auto` or matching padding).

### 2. Smart Name Search (`app/main.py`)

**Problem:** Users search "John Smith" but FTL stores "SMITH John". Search returns 0 results.
**Fix:** Update `_do_fencer_search` logic.
-   **Split Input:** If the query string has spaces (e.g., "John Smith"):
    -   Generate permutations: "SMITH John", "John SMITH", "SMITH, John".
    -   Search against the fencer name field using these permutations in addition to the raw query.
-   **Case Insensitivity:** Continue using case-insensitive matching.

### 3. Fix "Infinite Waiting" Bug (`app/services/tournament_service.py`)

**Problem:** Fencers in completed events are shown as "Waiting" (Screenshot 7).
**Root Cause:** The status logic likely checks "Is active?" -> No -> Default to "Waiting", without checking "Is event over?".
**Fix:**
-   In `_get_fencer_status` (or equivalent orchestration method):
    -   **Step 1:** Check if the fencer is in the `event_results` (final placements).
    -   **If Yes:** Return status "Finished" with their place immediately. Do NOT return "Waiting".
    -   **Step 2:** If not in results, *then* check if currently active on a strip.
    -   **Step 3:** If neither, return "Waiting" (only if event is not effectively "completed" for them).

### 4. Button Alignment (`app/templates/tournament_dashboard.html`)

**Problem:** "Add Fencer" and "Refresh" buttons are misaligned (Screenshot 5).
**Fix:**
-   The `.dashboard-actions` container is already flex, but the *forms* inside might be breaking it.
-   Ensure the `form` element for "Refresh" has `margin: 0` and `display: inline-flex`.
-   Apply the same `.btn` class or consistent styling to both the `<a>` (Add Fencer) and `<button>` (Refresh).
-   Verify heights are identical.

## Acceptance Criteria

- [ ] **Search UI:** Input box takes up available width and shows full text.
- [ ] **Smart Search:** Searching "John Smith" finds "SMITH John".
- [ ] **Status Logic:** Fencers in completed events show as "Finished" (Place X), not "Waiting".
- [ ] **Buttons:** "Add Fencer" and "Refresh" are perfectly aligned in height and baseline.
