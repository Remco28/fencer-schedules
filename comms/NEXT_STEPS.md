# Next Steps for Fencer Schedules

**Last Updated:** 2026-01-15
**Current Phase:** New Primary Flow Implementation

---

## Project Direction (Updated 2026-01-15)

The app is pivoting to a **tournament-centric, club-based tracking** model:

1. User enters a FencingTimeLive tournament URL
2. User sets their club (e.g., "Elite Fencers Club") and optional weapon filter
3. App automatically discovers all club fencers across all events
4. Consolidated dashboard shows all tracked fencers grouped by activity
5. Manual fencer add for non-club members

See `comms/plan.md` for full details.

---

## Completed Work (Foundation)

### FTL Parsers (94 tests)
- [x] Pool IDs extractor (`app/ftl/parsers/pool_ids.py`)
- [x] Pool HTML parser (`app/ftl/parsers/pools.py`)
- [x] Pool results JSON parser (`app/ftl/parsers/pool_results.py`)
- [x] DE tableau parser (`app/ftl/parsers/de_tableau.py`)

### HTTP Client
- [x] Retry/timeout logic (`app/ftl/client.py`)
- [x] TTL cache with force-refresh
- [x] Bulk parallel fetching

### Auth System
- [x] User registration and login
- [x] Session management
- [x] CSRF protection
- [x] Rate limiting

### UI Pages (Detail Views)
- [x] `/search` - Fencer search
- [x] `/pools` - Pool overview
- [x] `/advancement` - Advancement status
- [x] `/de` - DE tableau

---

## Next: Phase A - Research & Preparation

Before building the new flow, we need to research FTL's tournament-level pages.

### A1: Tournament Schedule Page Research
- [ ] Fetch sample HTML from `/tournaments/eventSchedule/{tournament_id}`
- [ ] Document HTML structure (event list, times, event IDs)
- [ ] Identify parsing strategy
- [ ] Save sample artifact to `comms/ftl_research_tournament_schedule.md`

### A2: Event Round Discovery Research
- [ ] For a sample event, find how pool_round_id is exposed
- [ ] For a sample event, find how de_round_id is exposed
- [ ] Document the discovery process
- [ ] Test with multiple events in different phases

### A3: Create Research Summary
- [ ] Document URL patterns
- [ ] Document parsing strategies
- [ ] Identify edge cases and risks

---

## Phase B - User Profile Enhancement

### B1: Add Club Field to User
- [ ] Add `club` column to User model
- [ ] Create database migration
- [ ] Update registration form (optional club input)

### B2: Profile Edit Page
- [ ] Create `/profile` page
- [ ] Allow editing username, email, club
- [ ] Add navigation link

---

## Phase C - Tournament Setup

### C1: Tournament Schedule Parser
- [ ] Implement parser for tournament schedule HTML
- [ ] Extract: event name, weapon, start time, event_id
- [ ] Add tests with sample artifact

### C2: Event Round Discovery
- [ ] Implement method to find pool_round_id for an event
- [ ] Implement method to find de_round_id for an event
- [ ] Handle events in different phases

### C3: Database Models
- [ ] Add TrackedTournament model
- [ ] Add CachedEvent model
- [ ] Add TrackedFencer model
- [ ] Create migrations

### C4: Tournament Setup Page
- [ ] Create `/tournament/new` page
- [ ] URL input and validation
- [ ] Club and weapon filter inputs
- [ ] Discover and display events

### C5: Club Fencer Discovery
- [ ] Fetch pool data for all matching events
- [ ] Filter fencers by club name
- [ ] Store discovered fencers

---

## Phase D - Consolidated Dashboard

### D1: Orchestration Layer
- [ ] Aggregate fencer status across all events
- [ ] Compute current location (strip, pool)
- [ ] Compute phase (pools, DE, complete)
- [ ] Compute result (advanced, eliminated, place)

### D2: Dashboard UI
- [ ] Create `/tournament/{id}` dashboard page
- [ ] Group fencers: Active Now, Waiting, Finished
- [ ] Show: name, event, location, status
- [ ] Add refresh button

### D3: Dashboard Navigation
- [ ] List user's tracked tournaments on `/dashboard`
- [ ] Link to individual tournament dashboards

---

## Phase E - Manual Fencer Tracking

### E1: Cross-Event Fencer Search
- [ ] Search by name across all events in tournament
- [ ] Display matching fencers with event info

### E2: Add/Remove Fencers
- [ ] Add fencer to TrackedFencer
- [ ] Remove fencer from tracking
- [ ] Distinguish club vs manual in UI

---

## Phase F - Polish & Cleanup

### F1: Auto-Cleanup
- [ ] Background job to delete expired tournaments (48h TTL)
- [ ] Clean up associated events and fencers

### F2: Error Handling
- [ ] Handle FTL unavailable gracefully
- [ ] Handle partial event data
- [ ] User-friendly error messages

### F3: Mobile Testing
- [ ] Test on mobile devices
- [ ] Fix responsive issues

### F4: Performance
- [ ] Profile dashboard load time
- [ ] Optimize queries and caching

---

## Existing Pages (Detail Views)

These pages will become drill-down views from the dashboard:

| Page | Route | Access |
|------|-------|--------|
| Pool Overview | `/pools` | Click fencer → see full pool |
| DE Tableau | `/de` | Click fencer → see full bracket |
| Search | `/search` | May deprecate or repurpose |
| Advancement | `/advancement` | May deprecate or integrate |

---

## Priority

🔥 **Phase A** (Research) - Must complete before building
⚡ **Phase B-D** - Core new functionality
📊 **Phase E** - Enhancement
💡 **Phase F** - Polish

**Current Priority:** 🔥 Phase A - Research tournament schedule page structure

---

## Quick Reference

| Doc | Purpose |
|-----|---------|
| `comms/plan.md` | Full development plan |
| `docs/ARCHITECTURE.md` | System architecture |
| `docs/ftl-api-specification.md` | FTL parsing guide |
| `comms/log.md` | Activity log |

---

*This file tracks immediate next steps. See `comms/plan.md` for overall direction.*
