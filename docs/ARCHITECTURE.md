# Fencer Schedules App - Architecture Overview

## System Purpose

A mobile-first web app for tracking fencers at live tournaments. Users enter a FencingTimeLive tournament URL, set their club, and see a consolidated dashboard of all club fencers across all events.

## System Components

### Core Services

- **WebApp** (`app/main.py`) - FastAPI application serving the web interface and API endpoints
- **FTL Parsers** (`app/ftl/parsers/`) - Parse HTML/JSON from FencingTimeLive into structured data
- **FTL Client** (`app/ftl/client.py`) - HTTP client with retry, timeout, and caching

### Supporting Services

- **Database** (`app/database.py`) - SQLite via SQLAlchemy for users, tournaments, and cached data
- **Auth Services** (`app/services/`) - Password hashing, session management, CSRF, rate limiting

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  UI Layer                                                       │
│  - Tournament setup page (enter URL, set filters)               │
│  - Consolidated dashboard (all tracked fencers)                 │
│  - Detail views (pools, DE tableau)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Orchestration Layer (NEW)                                      │
│  - Tournament schedule parser                                   │
│  - Event round discovery                                        │
│  - Club-based fencer aggregation                                │
│  - Status computation across events                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FTL Data Layer (COMPLETE)                                      │
│  - pool_ids.py: Extract pool IDs from event page                │
│  - pools.py: Parse pool HTML (fencers, strips, bouts)           │
│  - pool_results.py: Parse results JSON (advancement)            │
│  - de_tableau.py: Parse DE bracket (matches, scores)            │
│  - client.py: HTTP with retry/cache, bulk fetching              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Foundation Layer (COMPLETE)                                    │
│  - Auth: register, login, logout, sessions                      │
│  - Database: SQLAlchemy models, migrations                      │
│  - Templates: Jinja2, Pico CSS                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Main User Journey

```
User → Pastes tournament URL → WebApp validates URL
  ↓
WebApp → Fetches tournament schedule page → Parses events list
  ↓
WebApp → For each event: discovers pool_round_id, de_round_id
  ↓
WebApp → Fetches pool data for all events → Filters by club name
  ↓
WebApp → Aggregates fencer status across events
  ↓
WebApp → Renders consolidated dashboard (grouped by activity)
  ↓
User sees: Active Now | Waiting | Finished
```

## Data Flow: Dashboard Refresh

```
User → Clicks Refresh → WebApp receives request
  ↓
WebApp → Fetches fresh data for all tracked events (cache bypass optional)
  ↓
WebApp → Re-computes fencer statuses
  ↓
WebApp → Renders updated dashboard
```

## Key Entities

| Entity | Description |
|--------|-------------|
| **User** | App user with username, email, club affiliation |
| **TrackedTournament** | User's tournament with URL, club filter, weapon filter |
| **TrackedFencer** | Manually-added fencer (non-club) |
| **CachedEvent** | Tournament event with IDs, phase, last fetch time |

## FencingTimeLive Data Hierarchy

```
Tournament (tournament_id)
  └── Event (event_id) - e.g., "Senior Women's Epee"
        ├── Pool Round (pool_round_id)
        │     └── Pools 1-N
        │           └── Fencers, strips, bouts
        └── DE Round (de_round_id)
              └── Tableau matches
                    └── Seeds, scores, winners
```

## External Integration: FencingTimeLive

| Endpoint Pattern | Data Retrieved |
|------------------|----------------|
| `/tournaments/eventSchedule/{tournament_id}` | Event list, times, names |
| `/events/pools/{event_id}/{pool_round_id}` | Pool IDs (JavaScript) |
| `/pools/scores/{event_id}/{pool_id}` | Pool HTML (fencers, bouts) |
| `/pools/results/data/{event_id}/{pool_round_id}` | Results JSON (advancement) |
| `/tableaus/scores/{event_id}/{de_round_id}` | DE tableau HTML |

**Caching:** 3-minute TTL for active events. Manual refresh available.

**Error Handling:** Retry 3x with exponential backoff. 10-second timeout. 502/504 for upstream errors.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./fencer_schedules.db` | Database connection |
| `FTL_TIMEOUT` | `10` | HTTP timeout in seconds |
| `FTL_MAX_WORKERS` | `8` | Concurrent fetch threads |
| `FTL_CACHE_TTL` | `180` | Cache TTL in seconds |

## File Structure

```
app/
├── main.py              # FastAPI app, routes, handlers
├── database.py          # SQLAlchemy setup
├── models.py            # User, Session, Tournament models
├── crud.py              # Database operations
├── api/
│   ├── auth.py          # Auth routes
│   └── dependencies.py  # Auth dependencies, templates
├── services/
│   ├── auth_service.py  # Password hashing, sessions
│   ├── csrf_service.py  # CSRF tokens
│   └── rate_limit_service.py
├── ftl/
│   ├── client.py        # HTTP client, caching, bulk fetch
│   ├── schemas.py       # Pydantic models
│   └── parsers/
│       ├── pool_ids.py
│       ├── pools.py
│       ├── pool_results.py
│       └── de_tableau.py
├── templates/           # Jinja2 templates
└── static/              # CSS, JS assets

tests/
├── ftl/                 # Parser and client tests (94 tests)
├── api/                 # API endpoint tests
└── web/                 # Web UI tests
```

## Development Guidelines

- **Read this file** to understand component relationships
- **Run tests** before/after changes: `.venv/bin/pytest tests/`
- **Follow existing patterns** in handlers, services, parsers
- **Keep flows cohesive** - parsers return dicts, handlers orchestrate

## Related Docs

- Development Plan: `comms/plan.md`
- FTL API Spec: `docs/ftl-api-specification.md`
- Task Specs: `comms/tasks/`
- Activity Log: `comms/log.md`

---

*Last updated: 2026-01-15*
