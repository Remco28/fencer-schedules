# Next Steps

**Last Updated:** 2026-01-16
**Current Status:** Phase D (Consolidated Dashboard) complete and approved ✅
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

**Test Status:** 140/140 tests passing (zero regressions)

---

## What's Next: Phase E

### Phase E: Manual Fencer Tracking

**Goal:** Allow users to manually add fencers to track (beyond auto-discovered club members)

**Key Features:**
- Search for any fencer across all events in a tournament
- Add/remove fencers to tracking list
- Distinguish club-discovered vs manually-added fencers in dashboard
- TrackedFencer model to persist manual selections

**Why This Matters:**
- Users may want to track friends/rivals from other clubs
- Coaches may want to track specific competitors in their fencer's pools
- Flexibility beyond just club-based tracking

**Estimated Scope:**
- New `TrackedFencer` model (fencer_name, source="manual", tracked_tournament_id)
- Fencer search UI (search across all events for a name)
- Add/Remove buttons in dashboard or search results
- Dashboard UI updates to show source indicator
- ~15-20 tests (model + search + add/remove flows)

---

## Phase F: Polish & Cleanup (After Phase E)

**Remaining Tasks:**
- Auto-cleanup expired tournaments (48-hour TTL background job)
- Error handling edge cases and user-friendly messages
- Mobile responsiveness testing and fixes
- Performance optimization (if needed)
- Documentation for end users

---

## How to Continue

### For the Architect:

1. **Write Phase E Spec:**
   ```bash
   # Create spec file
   comms/tasks/2026-01-XX-phase-e-manual-fencer-tracking.md
   ```

2. **Spec Should Include:**
   - TrackedFencer model schema
   - Fencer search endpoint/UI mockup
   - Add/Remove fencer flow (UX wireframes)
   - Dashboard UI changes (visual indicators for manual vs club)
   - Acceptance criteria
   - Test requirements

3. **Review Current Dashboard:**
   - Look at `/tournament/{id}/dashboard` template
   - Consider where "Add Fencer" button should go
   - Design how to distinguish club vs manual fencers (icon, badge, color?)

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

3. **Read Phase E Spec** (once written)

---

## Key Files to Know

### Models
- `app/models.py` - User, TrackedTournament, CachedEvent

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
- `/profile` - User profile with club setting

### Templates
- `app/templates/tournament_dashboard.html` - Consolidated dashboard UI
- `app/templates/tournament_new.html` - Tournament setup form
- `app/templates/tournament_detail.html` - Event list

### Tests
- `tests/services/test_tournament_service.py` - Service orchestration tests
- `tests/web/test_tournament_dashboard.py` - Dashboard web tests
- `tests/web/test_tournament.py` - Tournament setup tests
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
| Manual Fencer Tracking | ⏳ Next Up | Not started |
| Auto-Cleanup | ⏳ Phase F | Not started |

**Total Tests:** 140 passing
**Total Lines:** ~7,500+ lines of code

---

## Architecture Notes for Phase E

### Current Flow:
```
User → Tournament URL → Auto-discover club fencers → Dashboard
```

### Phase E Will Add:
```
User → Tournament URL → Auto-discover club fencers → Dashboard
                                                          ↓
                                            [+ Add Fencer Button]
                                                          ↓
                                            Search all events
                                                          ↓
                                            Select fencer → Add to tracking
                                                          ↓
                                            Dashboard (club + manual fencers)
```

### Data Model Addition:
```python
class TrackedFencer(Base):
    __tablename__ = "tracked_fencers"

    id = Column(Integer, primary_key=True)
    tracked_tournament_id = Column(Integer, ForeignKey("tracked_tournaments.id"))
    fencer_name = Column(String(200), nullable=False)
    source = Column(String(20), default="manual")  # "club" or "manual"
    event_id = Column(String(32), nullable=True)  # Optional: specific event
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
```

### Dashboard Service Change:
```python
def get_tournament_fencer_status(...):
    # Current: Only fetch club-matched fencers
    # Phase E: ALSO fetch manually tracked fencers
    # Mark each FencerStatus with .source = "club" or "manual"
```

---

## Questions to Consider for Phase E

1. **UX:** Where should "Add Fencer" button be?
   - In dashboard header?
   - Next to each event in `/tournament/{id}` page?
   - Both?

2. **Search Scope:**
   - Search across all events in tournament?
   - Or let user pick specific event first?

3. **Visual Distinction:**
   - How to show club vs manual fencers?
   - Icon? Badge? Different color?

4. **Remove Flow:**
   - X button next to each manual fencer?
   - Confirmation dialog?

5. **Edge Cases:**
   - What if manually added fencer is also club member?
   - What if fencer name has typo? (fuzzy search?)

---

*Ready to start Phase E when you return!* 🚀
