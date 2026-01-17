# Next Steps

**Last Updated:** 2026-01-16
**Current Status:** Phase E (Manual Fencer Tracking) complete and approved ✅
**Branch:** `feature/tournament-dashboard`

---

## Where We Are Now

### ✅ Completed Phases

**Phase A: Research & Preparation**
- Researched FTL tournament schedule page structure
- Researched event page structure for round ID discovery
- Created research artifacts and parsing strategies

**Phase B: User Profile Enhancement**
- Added `club` field to User model
- Created profile edit page at `/profile`
- Migration for existing users
- 8 tests passing

**Phase C: Tournament Setup**
- Tournament schedule parser (extracts events from tournament page)
- Event rounds parser (discovers pool_round_id, de_round_id per event)
- TrackedTournament and CachedEvent models
- `/tournament/new` setup page with URL, club, and weapon filters
- `/tournament/{id}` detail page showing events
- Auto-discovery of club fencers across events
- 16 tests passing (7 parser + 9 web)

**Phase D: Consolidated Dashboard**
- Tournament service orchestration (`app/services/tournament_service.py`)
- Fencer status aggregation across all events
- `/tournament/{id}/dashboard` with activity grouping (active/waiting/finished)
- Location display (strip, pool number, DE round)
- DE placement logic (medals, eliminations)
- Centralized club matcher (`app/services/club_matcher.py`)
- Force refresh functionality
- 11 tests passing (5 service + 6 web)

**Phase E: Manual Fencer Tracking**
- Tracked fencer model and CRUD
- Tournament fencer search UI and add/remove tracking
- Manual source badges on dashboard
- Web tests for tracked fencers

**Test Status:** Not re-verified in this review

---

## What's Next: Phase F

### Phase F: Polish & Cleanup

**Remaining Tasks:**
- Auto-cleanup expired tournaments (48-hour TTL background job)
- Error handling edge cases and user-friendly messages
- Mobile responsiveness testing and fixes
- Performance optimization (if needed)
- Documentation for end users

---

## How to Continue

### For the Architect:

1. **Write Phase F Spec:**
   ```bash
   # Create spec file
   comms/tasks/2026-01-XX-phase-f-polish-and-cleanup.md
   ```

2. **Spec Should Include:**
   - Auto-cleanup strategy (TTL, job schedule, delete rules)
   - UX polish checklist and mobile breakpoints
   - Error copy refinements and fallback states
   - Performance targets (cache hits, fetch limits)
   - Test requirements

### For the Developer:

1. **Review Completed Work:**
   ```bash
   # Check out the feature branch
   git checkout feature/tournament-dashboard

   # Run all tests
   .venv/bin/pytest tests/ -v

   # Start the app to see Phase D dashboard
   .venv/bin/uvicorn app.main:app --reload
   ```

2. **Explore Dashboard:**
   - Navigate to `/tournament/new`
   - Enter a tournament URL (use test fixture data)
   - View the consolidated dashboard at `/tournament/{id}/dashboard`
   - Test refresh functionality

3. **Read Phase F Spec** (once written)

---

## Key Files to Know

### Models
- `app/models.py` - User, TrackedTournament, CachedEvent, TrackedFencer

### Services
- `app/services/tournament_service.py` - Fencer status orchestration
- `app/services/club_matcher.py` - Club matching logic
- `app/services/auth_service.py` - Authentication
- `app/services/rate_limit_service.py` - Rate limiting

### FTL Parsers (All Working)
- `app/ftl/parsers/tournament_schedule.py` - Parse tournament schedule page
- `app/ftl/parsers/event_rounds.py` - Extract pool/DE round IDs
- `app/ftl/parsers/pools.py` - Parse pool rosters and bout data
- `app/ftl/parsers/pool_results.py` - Parse advancement status
- `app/ftl/parsers/de_tableau.py` - Parse DE bracket

### Key Routes
- `/tournament/new` - Tournament setup form
- `/tournament/{id}` - Event list view
- `/tournament/{id}/dashboard` - Consolidated fencer dashboard (PHASE D)
- `/tournament/{id}/search` - Tournament-wide fencer search (PHASE E)
- `/profile` - User profile with club setting

### Templates
- `app/templates/tournament_dashboard.html` - Consolidated dashboard UI
- `app/templates/tournament_new.html` - Tournament setup form
- `app/templates/tournament_detail.html` - Event list
- `app/templates/tournament_search.html` - Manual fencer search

### Tests
- `tests/services/test_tournament_service.py` - Service orchestration tests
- `tests/web/test_tournament_dashboard.py` - Dashboard web tests
- `tests/web/test_tournament.py` - Tournament setup tests
- `tests/web/test_tracked_fencers.py` - Manual fencer tracking tests
- `tests/ftl/` - Parser tests (94 tests)
- `tests/api/` - API tests (11 tests)

---

## Project Status Summary

| Component | Status | Test Coverage |
|-----------|--------|---------------|
| FTL Parsers | ✅ Complete | 94 tests passing |
| HTTP Client | ✅ Complete | Included in parser tests |
| Auth System | ✅ Complete | 11 tests passing |
| User Profile | ✅ Complete | 8 tests passing |
| Tournament Setup | ✅ Complete | 16 tests passing |
| Consolidated Dashboard | ✅ Complete | 11 tests passing |
| Manual Fencer Tracking | ✅ Complete | Search/add/remove + dashboard badges |
| Auto-Cleanup | ⏳ Phase F | Not started |

**Total Tests:** Not re-verified in this review
**Total Lines:** ~7,500+ lines of code

---

## Phase F Focus Areas

1. **Auto-cleanup:** Define TTL rules and data pruning strategy.
2. **UX polish:** Mobile responsiveness and layout refinements.
3. **Error handling:** Human-friendly messaging and retry guidance.
4. **Performance:** Cache tuning and fetch limits.
5. **Documentation:** User-facing guide for setup and tracking.

---

*Ready to start Phase F when you return!* 🚀
