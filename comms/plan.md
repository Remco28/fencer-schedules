# Fencer Schedules App - Development Plan

## 1. Vision

A **mobile-first web app** for coaches, parents, and clubmates to track fencers at live tournaments. The app answers:

- **Where is my fencer?** (strip assignment, pool number)
- **What's their status?** (active bout, waiting, advanced, eliminated)
- **How are they doing?** (pool results, DE progress, final placement)

### Core Concept

Users enter a **tournament URL** from FencingTimeLive, set their **club**, and the app automatically tracks all club members across all events. Additional fencers can be tracked manually.

### Key User Journey

```
1. User logs in
2. User pastes a FencingTimeLive tournament URL
3. User sets club filter (e.g., "Elite Fencers Club") and optional weapon filter
4. App discovers all events and finds club fencers automatically
5. User sees a consolidated dashboard:
   - All tracked fencers across all events
   - Current location (strip, pool) and status
   - Grouped by activity (active now, waiting, finished)
6. User can manually add non-club fencers to track
7. Dashboard updates on refresh
```

---

## 2. Architecture Overview

### Data Hierarchy (FencingTimeLive)

```
Tournament (e.g., "Capital Clash 2026")
  └── Event (e.g., "Senior Women's Epee")
        ├── Pool Round (pool_round_id)
        │     └── Pools 1-N (fencers, strips, bouts)
        └── DE Round (de_round_id)
              └── Tableau (matches, scores, brackets)
```

### System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW: Orchestration Layer                                       │
│  - Tournament schedule parser                                   │
│  - Event round discovery                                        │
│  - Club-based fencer aggregation                                │
│  - Consolidated dashboard                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXISTING: FTL Data Layer (fully built)                         │
│  - Pool parser (fencers, strips, bouts)                         │
│  - Pool results parser (advancement status)                     │
│  - DE tableau parser (matches, scores)                          │
│  - HTTP client with retry/cache                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXISTING: Foundation Layer (fully built)                       │
│  - User authentication (register, login, sessions)              │
│  - Database (SQLAlchemy + SQLite)                               │
│  - Base UI templates and styling                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### User

```
User
  - id, username, email, password_hash
  - club (string, nullable) ← NEW: user's home club for auto-tracking
  - created_at, updated_at
```

### Tournament Tracking (NEW)

```
TrackedTournament
  - id
  - user_id (FK → User)
  - tournament_id (32-char hex from FTL URL)
  - tournament_name (scraped or user-provided)
  - tournament_url (original FTL URL)
  - club_filter (string, nullable) - defaults to user's club
  - weapon_filter (string, nullable) - e.g., "Epee" or null for all
  - created_at
  - expires_at (auto-delete after 48 hours)

TrackedFencer
  - id
  - tracked_tournament_id (FK → TrackedTournament)
  - fencer_name (string)
  - source ("club" = auto-discovered, "manual" = user-added)
  - created_at
```

### Event Cache (NEW)

```
CachedEvent
  - id
  - tournament_id
  - event_id (32-char hex)
  - event_name (e.g., "Senior Women's Epee")
  - weapon (e.g., "Epee", "Foil", "Saber")
  - start_time (datetime, nullable)
  - pool_round_id (32-char hex, nullable)
  - de_round_id (32-char hex, nullable)
  - phase (not_started, pools, de, complete)
  - last_fetched_at
```

---

## 4. Implementation Phases

### Phase A: Research & Preparation
- [ ] Research tournament schedule page HTML structure
- [ ] Research event page structure (how to find pool/DE round IDs)
- [ ] Document URL patterns and parsing strategies
- [ ] Create sample data artifacts

### Phase B: User Profile Enhancement
- [ ] Add `club` field to User model
- [ ] Create profile edit page
- [ ] Migration for existing users

### Phase C: Tournament Setup
- [ ] Tournament schedule parser (extract events from tournament page)
- [ ] Event round discovery (find pool_round_id, de_round_id per event)
- [ ] TrackedTournament and CachedEvent models
- [ ] Tournament setup page (enter URL, set filters)
- [ ] Auto-discover club fencers across events

### Phase D: Consolidated Dashboard
- [ ] Orchestration layer (aggregate fencer status across events)
- [ ] Dashboard UI with groupings (active, waiting, finished)
- [ ] Fencer status computation (location, phase, result)
- [ ] Manual refresh functionality

### Phase E: Manual Fencer Tracking
- [ ] Cross-event fencer search
- [ ] TrackedFencer model and add/remove UI
- [ ] Distinguish club vs manual fencers in dashboard

### Phase F: Polish & Cleanup
- [ ] Auto-cleanup expired tournaments (48-hour TTL)
- [ ] Error handling and edge cases
- [ ] Mobile responsiveness testing
- [ ] Performance optimization

---

## 5. Existing Assets (Completed)

### FTL Parsers (94 tests passing)
| Parser | File | Purpose |
|--------|------|---------|
| Pool IDs | `app/ftl/parsers/pool_ids.py` | Extract pool IDs from event page |
| Pool HTML | `app/ftl/parsers/pools.py` | Parse fencers, strips, bouts |
| Pool Results | `app/ftl/parsers/pool_results.py` | Parse advancement status |
| DE Tableau | `app/ftl/parsers/de_tableau.py` | Parse elimination bracket |

### HTTP Client
| Component | File | Purpose |
|-----------|------|---------|
| Client | `app/ftl/client.py` | Retry, timeout, TTL cache |
| Bulk Fetch | `app/ftl/client.py` | Parallel pool fetching |

### Auth System
| Component | File | Purpose |
|-----------|------|---------|
| Auth Routes | `app/api/auth.py` | Register, login, logout |
| Services | `app/services/` | Password hashing, CSRF, rate limits |

### UI Pages (may become detail views)
| Page | Route | Purpose |
|------|-------|---------|
| Search | `/search` | Find fencer by name |
| Pools | `/pools` | View pool rosters |
| Advancement | `/advancement` | View advancement status |
| DE Tableau | `/de` | View elimination bracket |

---

## 6. UI Mockup: Consolidated Dashboard

```
╔══════════════════════════════════════════════════════════════════╗
║  Capital Clash 2026                                  [Refresh]   ║
║  Elite Fencers Club · Epee events                                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ACTIVE NOW (2)                                                  ║
║  ┌────────────────────────────────────────────────────────────┐  ║
║  │ Jane Smith      │ W. Epee  │ Strip A5 │ DE Table of 16    │  ║
║  │ Mike Chen       │ M. Epee  │ Pool 7   │ Bout 3 of 6       │  ║
║  └────────────────────────────────────────────────────────────┘  ║
║                                                                  ║
║  WAITING (1)                                                     ║
║  ┌────────────────────────────────────────────────────────────┐  ║
║  │ Bob Johnson     │ M. Epee  │ —        │ Starts 2:00 PM    │  ║
║  └────────────────────────────────────────────────────────────┘  ║
║                                                                  ║
║  FINISHED (2)                                                    ║
║  ┌────────────────────────────────────────────────────────────┐  ║
║  │ Alice Wong      │ W. Epee  │ —        │ Eliminated (Pools)│  ║
║  │ Tom Davis       │ W. Epee  │ —        │ 3rd Place         │  ║
║  └────────────────────────────────────────────────────────────┘  ║
║                                                                  ║
║  [+ Add fencer manually]                                         ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 7. Technical Decisions

### Club Matching Strategy
- Primary: exact match on club name
- Fallback: case-insensitive substring match
- User can confirm/reject matches during setup

### Data Freshness
- Manual refresh (button click)
- Cache TTL: 3 minutes for active events
- Future: auto-refresh every 60 seconds (optional)

### Data Retention
- Tournament data auto-expires 48 hours after creation
- Background job cleans up expired records
- No long-term historical storage (live tracking focus)

### Existing Pages
- Keep as "detail views" accessible from dashboard
- Click fencer → see full pool roster or DE bracket
- May hide from main nav (dashboard is primary entry)

---

## 8. Open Questions

1. **Tournament schedule parsing**: Need to research FTL's `/tournaments/eventSchedule/{id}` page structure
2. **Event round discovery**: How to programmatically find pool_round_id and de_round_id for each event
3. **Club name variations**: How strict should matching be? User confirmation step?
4. **Event phases**: How to detect if an event is in pools vs DE vs complete

---

## 9. Success Criteria

- [ ] User can paste tournament URL and see all club fencers automatically
- [ ] Dashboard shows real-time status across multiple events
- [ ] Manual fencer add works for tracking non-club members
- [ ] Data is cleaned up automatically after 48 hours
- [ ] Mobile-friendly and fast to use at a tournament

---

*Last updated: 2026-01-15*
