# Task: Phase H — High Fidelity Styling (App Feel)

**Date:** 2026-01-29
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

The previous "card" implementation resulted in a flat, web-1.0 look. This task is to apply **High Fidelity Styling** to transform the application into a modern mobile interface. We will move away from default Pico CSS aesthetics by overriding variables and enforcing a strict "Layered" material design.

## Core Design Concept

-   **App Shell:** The page background must be **Light Gray** (`#f0f2f5`).
-   **Surface:** Content containers (Cards, Navbar) must be **Pure White** (`#ffffff`) or **Brand Color**.
-   **Depth:** Elements must separate from the background using **Soft Shadows**, not borders.
-   **Density:** Compact spacing to show more data on mobile screens.

## Required Changes

### 1. Global Styles (`app/static/styles.css`)

**A. Variables & Reset**
Override the root variables to enforce the new palette:
```css
:root {
    --background-color: #f0f2f5; /* Light gray app background */
    --card-bg: #ffffff;
    --primary: #2c3e50; /* Deep Blue/Slate for Nav */
    --primary-hover: #34495e;
    --accent: #3498db; /* Bright Blue for Actions */
    --text-main: #2c3e50;
    --text-muted: #95a5a6;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.05);
    --radius-card: 12px;
}

body {
    background-color: var(--background-color);
    color: var(--text-main);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
```

**B. Navigation Bar**
Transform the header into a solid App Bar.
-   Background: `var(--primary)` (Deep Blue).
-   Text: White.
-   Shadow: `var(--shadow-md)`.
-   Layout: Sticky top (`position: sticky; top: 0; z-index: 100;`).
-   Links: White text, no underline. "Log out" button should be a subtle transparent ghost button.

**C. Card Component (The Critical Fix)**
The previous "cards" had no depth. Implement this exact style:
```css
.fencer-card, .tournament-card {
    background: var(--card-bg);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-sm);
    border: none; /* Remove default borders */
    padding: 1rem;
    margin-bottom: 0.75rem;
    transition: transform 0.1s ease;
}

.fencer-card:active, .tournament-card:active {
    transform: scale(0.98); /* Tactile click feedback */
}
```

**D. Tournament List (Dashboard)**
-   Remove the "bullet list" look entirely.
-   Each tournament is a block-level `.tournament-card`.
-   **Title:** Bold, larger size (`1.1rem`).
-   **Subtitle:** Muted text for club/date.
-   **Action:** Add a visible chevron icon (`›`) on the right edge.

**E. Active Fencer Card**
-   **Highlight:** Give the "Active" cards a distinct left border or subtle background tint (`#f8fbff`).
-   **Location Badge:** Make the "Strip X" / "Pool Y" indicators **Large** and **Boxed**.
    ```css
    .location-box {
        background: #e3f2fd;
        color: #0d47a1;
        padding: 0.5rem 0.75rem;
        border-radius: 8px;
        font-weight: bold;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        line-height: 1;
    }
    .location-label { font-size: 0.7rem; text-transform: uppercase; opacity: 0.7; }
    .location-value { font-size: 1.4rem; }
    ```

**F. Empty States**
-   Replace text "No fencers currently active" with a styled container.
-   Background: Transparent or very light grey.
-   Border: Dashed light grey.
-   Content: Centered text + a simple emoji or icon (e.g., 🤺 or 💤).

### 2. Template Updates

**`base.html`**
-   Ensure `<nav>` is inside a container that spans the full width, or style the `<header>` to be full width with the dark background.

**`dashboard.html` (Main)**
-   Ensure the loop of tournaments produces `<div class="tournament-card">` elements (wrapped in `<a>` tags is fine, but style the container).
-   Style the "Add Tournament" button as a Floating Action Button (FAB) or a prominent full-width block at the bottom? -> *Keep it as a prominent block button at the top for now.*

**`tournament_dashboard.html`**
-   **Header:** Reduce padding. Make the tournament title H5 or H6 size, not H1. It takes up too much space.
-   **Group Headers:** styled H6 with uppercase tracking (`text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);`).

## Acceptance Criteria

1.  **Contrast:** The app clearly looks like "White Cards on Light Gray Background".
2.  **Navigation:** The top bar is Dark Blue with White text.
3.  **Depth:** Cards have a subtle shadow.
4.  **Touch:** Entire cards are clickable (where appropriate).
5.  **Hierarchy:** "Active" strip numbers are the largest text elements on the screen.
6.  **Polished Empty States:** Dashed borders or icons for empty lists.

## Reference
Think "iOS Settings" or "Google Now" cards. Clean, white, elevated.
