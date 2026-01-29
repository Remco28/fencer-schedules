# Next Steps

**Last Updated:** 2026-01-23
**Current Status:** All core phases complete, legacy UI removed
**Branch:** `main`

---

## Where We Are Now

The fencer tracking application is feature-complete with a clean, focused UI.

### Completed Phases

**Phase A: Research & Preparation**
- FTL tournament schedule page structure research
- Event page structure for round ID discovery
- Research artifacts and parsing strategies

**Phase B: User Profile Enhancement**
- `club` field on User model
- Profile edit page at `/profile`

**Phase C: Tournament Setup**
- Tournament schedule parser
- Event rounds parser (discovers pool_round_id, de_round_id)
- TrackedTournament and CachedEvent models
- `/tournament/new` setup page with URL, club, and weapon filters
- `/tournament/{id}` detail page showing events
- Auto-discovery of club fencers

**Phase D: Consolidated Dashboard**
- Tournament service orchestration
- Fencer status aggregation across all events
- `/tournament/{id}/dashboard` with activity grouping (active/waiting/finished)
- Location display (strip, pool number, DE round)
- DE placement logic (medals, eliminations)
- Force refresh functionality

**Phase E: Manual Fencer Tracking**
- TrackedFencer model and CRUD
- `/tournament/{id}/search` for finding fencers
- Add/remove tracking with source badges on dashboard

**Phase F: TTL Cleanup**
- `last_accessed_at` and `archived_at` fields
- On-request cleanup (48h TTL default)
- Restore flow for archived tournaments
- Archived badge and restore button in UI

**Phase G-I: Visual Polish (In Progress)**
- Phase G: Mobile-first card structure (Archived)
- Phase H: High fidelity styling (Archived)
- Phase I: Layout density & Nav polish (Active)
    - Compact fencer cards for lists
    - Cleaned up navbar
    - Aligned buttons

**UX Cleanup**
- Removed legacy hex-ID pages (`/search`, `/pools`, `/advancement`, `/de`)
- Simplified navigation: Dashboard, Track Tournament, Profile

---

## Current Application Flow

1. **Register/Login** → `/register`, `/login`
2. **Dashboard** → `/dashboard` - list of tracked tournaments
3. **Track Tournament** → `/tournament/new` - enter FTL URL, set filters
4. **Tournament Dashboard** → `/tournament/{id}/dashboard` - live fencer status
5. **Search Fencers** → `/tournament/{id}/search` - find and track individuals
6. **Profile** → `/profile` - update club name

---

## Test Status

**163 tests passing** across:
- FTL parsers (94 tests)
- API endpoints (11 tests)
- Web routes (58 tests)

Run tests: `.venv/bin/pytest`

---

## Key Files

### Models
- `app/models.py` - User, TrackedTournament, CachedEvent, TrackedFencer

### Services
- `app/services/tournament_service.py` - Fencer status orchestration
- `app/services/cleanup_service.py` - TTL archival
- `app/services/club_matcher.py` - Club matching logic

### FTL Parsers
- `app/ftl/parsers/tournament_schedule.py`
- `app/ftl/parsers/event_rounds.py`
- `app/ftl/parsers/pools.py`
- `app/ftl/parsers/pool_results.py`
- `app/ftl/parsers/de_tableau.py`

### Key Routes
- `/dashboard` - User's tournament list
- `/tournament/new` - Add tournament
- `/tournament/{id}/dashboard` - Live fencer tracking
- `/tournament/{id}/search` - Find fencers to track
- `/profile` - User settings

---

## Potential Future Work

- **Event drill-down**: Link from dashboard to detailed pool/DE views
- **Mobile optimization**: Test and refine responsive layouts
- **Notifications**: Alert when tracked fencer becomes active
- **Multi-user sharing**: Share tournament tracking with others
- **Performance**: Caching improvements if needed

---

## Quick Start

```bash
# Start the app
.venv/bin/uvicorn app.main:app --reload

# Run tests
.venv/bin/pytest

# Check test coverage
.venv/bin/pytest --cov=app
```

---

*Application is ready for use!*
