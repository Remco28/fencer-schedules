# Task: Phase K — Button Alignment & Iconography

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Finalize the dashboard UI by fixing the persistent misalignment between the "Add Fencer" and "Refresh" buttons, and updating the Refresh button to use a more modern icon/emoji.

## Required Changes

### 1. Update Refresh Button (`app/templates/tournament_dashboard.html`)

**Change:**
-   Update the "Refresh" button text from "Refresh" to `🔄️`.
-   Add an `aria-label="Refresh Dashboard"` for accessibility.
-   Ensure the button has the class `btn small outline` to match the "Add Fencer" link.

### 2. Force Button Alignment (`app/static/styles.css`)

**Problem:** Different element types (`<a>` vs `<button>` inside `<form>`) are baseline-misaligned and have different total heights.

**CSS Fixes:**
-   In `.dashboard-actions`:
    -   Ensure `display: flex; gap: 0.5rem; align-items: center;`.
-   In `.dashboard-actions form`:
    -   Force `margin: 0; display: inline-flex; align-items: center; vertical-align: middle;`.
-   In `.btn`:
    -   Ensure a fixed `height: 38px;` (or similar) is applied to both `small` buttons to prevent variations between `<a>` and `<button>`.
    -   Use `box-sizing: border-box;`.
    -   Enforce `line-height: 1;`.

### 3. Polish Dashboard Header Layout (`app/templates/tournament_dashboard.html`)

**Adjustment:**
-   If the "Refresh" button is now just an icon, we can make the container even tighter.
-   Ensure the `dashboard-header` wraps nicely on mobile so the title doesn't get crushed by the buttons.

## Acceptance Criteria

- [ ] **Icon:** The Refresh button displays `🔄️` instead of "Refresh".
- [ ] **Alignment:** The tops and bottoms of "Add Fencer" and the Refresh button are perfectly level.
- [ ] **Accessibility:** The Refresh button has an `aria-label`.
- [ ] **Regression:** All functionality (search, reload) still works.
