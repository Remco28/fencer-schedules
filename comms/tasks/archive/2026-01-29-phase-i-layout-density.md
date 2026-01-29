# Task: Phase I — Layout Density & Nav Polish

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Refine the UI introduced in Phase H. The current implementation suffers from a "messy" navigation bar and low data density in the "Finished" and "Waiting" lists, requiring excessive scrolling.

## Required Changes

### 1. Navigation Bar Cleanup (`app/static/styles.css` & `app/templates/base.html`)

**Problem:** The navbar elements are floating haphazardly. The "Log Out" button is too large.
**Goal:** A tight, single-row header.

**CSS Changes:**
-   Target `nav` inside `header`.
-   Ensure it uses `display: flex; justify-content: space-between; align-items: center;`.
-   **Brand:** `.brand` class for "Fencer Schedules" (Bold, White, No decoration).
-   **Links:** Container for links should be `display: flex; gap: 1rem; align-items: center;`.
-   **Log Out:**
    -   Remove the border/outline styles.
    -   Make it look like a text link: `color: rgba(255,255,255,0.8);`.
    -   On hover: `color: white;`.
    -   Remove the button padding so it aligns with text links.

**HTML Changes (`base.html`):**
-   Wrap the links in a specific container if needed to ensure they stay together on the right side.
-   Simplified structure:
    ```html
    <nav>
      <a href="/" class="brand">Fencer Schedules</a>
      <div class="nav-links">
         <a href="/dashboard">Dashboard</a>
         <!-- ... -->
         <form...><button class="link-button">Log out</button></form>
      </div>
    </nav>
    ```

### 2. Action Buttons Alignment (`app/templates/tournament_dashboard.html`)

**Problem:** "Add Fencer" and "Refresh" buttons are slightly misaligned.
**Fix:**
-   Wrap them in a flex container: `.dashboard-actions { display: flex; gap: 0.5rem; align-items: center; }`
-   Ensure both buttons have the same `height` or `line-height`.

### 3. Compact Cards for Waiting/Finished (`app/static/styles.css`)

**Problem:** "Finished" cards are too tall, wasting vertical space.
**Goal:** Dense list where you can see 8-10 fencers at once.

**CSS Changes:**
-   Create `.fencer-card.compact`:
    -   **Padding:** Reduce to `0.5rem 0.75rem`.
    -   **Layout:** Use Flexbox `display: flex; justify-content: space-between; align-items: center;`.
    -   **Typography:**
        -   Name: `font-size: 1rem; font-weight: 600;`.
        -   Subtext (Club/Event): `font-size: 0.8rem; color: var(--text-muted);` (display below name or hidden if very tight).
    -   **Result Badge:** Keep it, but ensure it sits on the right side, vertically centered.

**HTML Changes (`tournament_dashboard.html`):**
-   Update the loop for `grouped_fencers.waiting` and `grouped_fencers.finished`.
-   Use the new structure:
    ```html
    <!-- Compact Card Structure -->
    <div class="fencer-card compact">
        <div class="fencer-info">
            <div class="fencer-name">Name</div>
            <div class="fencer-detail">Event Name</div>
        </div>
        <div class="fencer-status">
            <span class="badge">Place: 15</span>
        </div>
    </div>
    ```

### 4. Active Section (No Changes)
-   Keep the large cards for "Active Now" (Phase H style). These *should* be big.

## Acceptance Criteria

- [ ] **Navbar:** Single row, distinct brand on left, links on right. "Log Out" looks like a link, not a button.
- [ ] **Buttons:** "Add Fencer" and "Refresh" are perfectly aligned.
- [ ] **Density:** "Finished" list shows fencers as slim rows (max ~50px height per item).
- [ ] **Mobile:** Navbar links wrap gracefully or stay concise on small screens.
