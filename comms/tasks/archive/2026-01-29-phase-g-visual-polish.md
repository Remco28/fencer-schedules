# Task: Phase G — Visual Polish (Mobile-First Card Design)

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Transform the current table-heavy "database viewer" UI into a modern, mobile-first application using a **Card-Based Interface**. The goal is to make the dashboard highly readable on small screens, increasing "glanceability" for fencers and parents running between strips.

## Principles

1.  **Mobile First:** Design for 360px width first. No wide tables.
2.  **Visual Hierarchy:** "Active" items must pop. "Waiting" and "Finished" should be secondary.
3.  **Glanceability:** Use icons and large text for critical info (Strip #, Pool #).
4.  **Touch Targets:** Buttons and links must be finger-friendly (>44px height).

## Changes Required

### 1. Styles (`app/static/styles.css`)

Refactor to support a card grid system.

*   **New Components:**
    *   `.fencer-card`: Base card container (padding, radius, shadow/border).
    *   `.fencer-card.active`: Highlighted style (e.g., green border, slight background tint).
    *   `.fencer-card.waiting`: Neutral style.
    *   `.fencer-card.finished`: Muted/Greyscale style.
    *   `.card-header`: Flex container for Name + Club.
    *   `.card-body`: Grid for location/status info.
    *   `.stat-badge`: Large, distinct badge for "Strip 5" or "Pool 2".
    *   `.action-row`: Bottom row for buttons (Untrack).

*   **Typography:**
    *   Increase font size for Names (1.1rem) and Strip Numbers (1.5rem).
    *   Use muted text for secondary info (Club, Event Name).

*   **Variables:**
    *   Define semantic colors (e.g., `--color-active`, `--color-waiting`, `--color-eliminated`).

### 2. Dashboard Template (`app/templates/dashboard.html`)

*   **Tournament List:**
    *   Convert the `<ul>` list of tournaments into a stack of clickable cards.
    *   Each card should show: Name, Club Filter (if any), Date/Time (Last Updated).
    *   Add a distinct "chevron" or arrow icon to indicate clickability.

### 3. Tournament Dashboard (`app/templates/tournament_dashboard.html`)

*   **Header:**
    *   Make sticky if possible (or just compact).
    *   Put "Refresh" button in a prominent, easy-to-hit location.

*   **"Active Now" Section:**
    *   **REMOVE** the `<table>`.
    *   **ADD** a `<div class="card-grid">`.
    *   **Card Content:**
        *   **Top:** Fencer Name (Bold), Club (Small).
        *   **Middle:** HUGE visual indicators for location.
            *   Example: A box saying "STRIP 5" next to "POOL 2".
        *   **Bottom:** Status text ("Fencing Pools").

*   **"Waiting" Section:**
    *   Convert to compact cards or a "List Group".
    *   Show Name and Event.
    *   Status should be simple: "Waiting".
    *   Keep the "Untrack" (X) button accessible but not accidental.

*   **"Finished" Section:**
    *   Compact list items.
    *   Greyed out visuals.
    *   Clear "Place: X" or "Result: V/D" badge.

### 4. Icons

Use generic SVG icons (no external library, just inline SVGs or a small sprite) for:
*   Strip (Map pin or square)
*   Pool (Group/Users)
*   Clock (Waiting)
*   Check/Trophy (Finished)

## Technical Constraints

*   **CSS Framework:** Continue using Pico CSS as the base reset/grid, but override heavily for the card components.
*   **Performance:** No heavy JS libraries. CSS-only layout.
*   **Responsiveness:** Must look good on mobile and desktop. Grid should go from 1 column (mobile) to 2-3 columns (desktop).

## Example Markup Structure (Guidance)

```html
<div class="fencer-grid">
  <!-- Active Card Example -->
  <article class="fencer-card active">
    <div class="card-header">
      <h3>Jane Doe</h3>
      <span class="club-tag">Generic FC</span>
    </div>
    <div class="card-location">
      <div class="location-badge strip">
        <span class="label">STRIP</span>
        <span class="value">5</span>
      </div>
      <div class="location-badge pool">
        <span class="label">POOL</span>
        <span class="value">2</span>
      </div>
    </div>
    <div class="card-status">
       On Strip / Fencing
    </div>
  </article>
</div>
```

## Acceptance Criteria

- [ ] Dashboard (`/dashboard`) lists tournaments as clickable cards.
- [ ] Tournament View (`/tournament/{id}/dashboard`) uses cards instead of tables.
- [ ] "Active" fencers are visually distinct and prominent.
- [ ] Strip/Pool numbers are large and easy to read at a glance.
- [ ] Mobile view (narrow width) shows a single column of cards.
- [ ] Desktop view shows a grid of cards.
- [ ] No regression in functionality (Delete/Refresh/Untrack still work).
