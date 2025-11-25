# Fencer Scheduling App - Development Plan

## 1. Objective

Build a **mobile-first**, read-only web app for coaches, parents, and clubmates to quickly answer:
- Where is each fencer right now? (pool/strip or DE tableau location)
- What is their status? (active, bout in progress, advanced, eliminated)
- What’s next? (upcoming bout/tableau position)

Scope clarifications:
- No email notifications or digests.
- Live data comes from FencingTimeLive scraping; registration notifications from the legacy kickstart are out-of-scope.
- The `project_kickstart/` codebase is a temporary reference; we will extract what we need, then retire/remove it.

## 2. Phased Rollout Plan

The new live-tracking requirement adds complexity. We will approach this in phases to deliver value incrementally and manage risk.

### Phase 1: Core Personalized Schedule (MVP)

Goal: Deliver the core, non-live schedule viewing experience.

- [ ] **User Authentication:**
    - [ ] User registration and login.
    - [ ] Ability for a user to set their home club.
- [ ] **Fencer Tracking:**
    - [ ] A page to search for fencers by name and club.
    - [ ] A mechanism to "track" or "untrack" individual fencers.
- [ ] **Static Schedule View:**
    - [ ] A page listing available tournaments (from `fencingtracker.com`).
    - [ ] On selecting a tournament, display a personalized schedule showing only club members and tracked fencers, with event times.

### Phase 2: Live Tracking via Manual Linking

Goal: Integrate live data from `fencingtimelive.com` using a user-provided URL (no email or push).

- [ ] **Event Linking:**
    - [ ] In the schedule view, add an input field for each event where a user can paste the corresponding `fencingtimelive.com` URL.
    - [ ] Store this URL in the database.
- [ ] **Live Data Scraper Service:**
    - [ ] Build or extend a scraper to parse a `fencingtimelive.com` event page.
    - [ ] Extract and serve:
        - [ ] Pool strip assignments and bout state.
        - [ ] Pool completion status and promotions.
        - [ ] DE tableau positions, match results, and strip assignments.
        - [ ] Fencer elimination/advancement status.
- [ ] **Dynamic "Live" Views:**
    - [ ] Mobile-first views for: fencer search, “where is my fencer?” (current strip/bout), and advancement status.
    - [ ] Indicators: `On Strip: A5`, `Waiting`, `Advanced`, `Eliminated`.
    - [ ] Manual refresh acceptable for MVP; auto-refresh optional.

## 3. Future Goals (Post-MVP)

- **Automatic Event Matching:** Investigate methods to automatically find the `fencingtimelive.com` URL for an event, removing the need for manual user input.

## 4. Technical Approach & Considerations

- **Frontend:** Continue with a mobile-first, server-rendered HTML approach using a responsive framework. A full-page reload will be the mechanism for refreshing live data, simplifying the initial frontend implementation.
- **Backend:**
    - The `scraper_service` will need significant updates to support `fencingtimelive.com`. This is a high-risk area; we must investigate the target site's structure carefully.
    - New API endpoints will be needed (e.g., `POST /api/events/{id}/set-live-url`, `GET /api/events/{id}/live-data`).
- **Database:**
    - The `events` table (or equivalent) will likely need a new column: `live_event_url` (nullable text).
    - Consider caching live data results to avoid excessive scraping.

## 5. Action Plan (Revised)

1.  **Task 1: Build Phase 1 (Core Schedule).**
    - Focus exclusively on implementing the non-live features from Phase 1. This provides a stable base.
2.  **Task 2: Investigate `fencingtimelive.com` Scraper.** ✅ **COMPLETE (2025-11-20)**
    - ✅ Analyzed structure of live event pages
    - ✅ Identified all required data sources (pool IDs, pool data, pool results, DE tableau)
    - ✅ Tested extraction methods with real tournament data
    - ✅ Documented complete API specification in `docs/ftl-api-specification.md`
    - ✅ **Verdict: FEASIBLE - Phase 2 is GO!**
3.  **Task 3: Build Phase 2 (Live Tracking).**
    - Implement the backend scraper service
    - Build parsers for pool and DE data
    - Add caching layer
    - Create API endpoints for frontend
    - Build frontend UI for live tracking

**Research Documentation:**
- **Technical Spec:** `docs/ftl-api-specification.md` - Complete implementation guide
- **Research Summary:** `comms/ftl_research_summary.md` - Executive summary of findings
- **Sample Data:** `comms/ftl_research_human*.md` - Real tournament data samples

---
*This is an iterative plan. We will update it as we go.*
*Last updated: 2025-11-20*
