# Project Manifest: Fencer Schedules App

**Purpose:** This file acts as a "map" for AI coding agents. It provides a stable set of pointers to critical project documentation and context, allowing the AI to quickly orient itself at the start of a new session.

**Last Updated:** 2026-01-29

---

## 1. Core Identity (Stable)
*These files define the project's high-level architecture, goals, and the roles of the participants. They should change infrequently.*

- **Development Plan:** `comms/plan.md` - Vision, user journey, implementation phases, data model
- **Architecture:** `docs/ARCHITECTURE.md` - System components, data flows, file structure
- **Deployment Guide:** `docs/DEPLOYMENT.md` - Hetzner/Coolify setup instructions
- **Backup Guide:** `docs/BACKUP_AND_RESTORE.md` - Data safety strategies
- **FTL API Specification:** `docs/ftl-api-specification.md` - Complete technical specification for FencingTimeLive parsing
- **Agent Roles:** `comms/roles/ARCHITECT.md`, `comms/roles/TECHADVISOR.md`

## 2. Dynamic State (Volatile)
*These files and directories reflect the current status, recent work, and active tasks. The AI should check these to understand what's happening right now.*

- **Activity Log:** `comms/log.md` - Chronological record of major development activities
- **Current Next Steps:** `comms/NEXT_STEPS.md` - Immediate action items and priorities
- **Current Phase:** Phase I (Layout Density & Nav Polish)
- **Current Branch:** `feature/visual-polish`
- **Active Task Spec:** `comms/tasks/2026-01-29-phase-i-layout-density.md`
- **Archived Task Specs:** `comms/tasks/archive/` (Phases A-F complete, G/H archived)

## 3. Project Vision (Updated 2026-01-15)

**Core Concept:** Tournament-centric, club-based fencer tracking

**User Journey:**
1. User logs in
2. User pastes FencingTimeLive tournament URL
3. User sets club filter and optional weapon filter
4. App discovers all club fencers across all events
5. Consolidated dashboard shows all tracked fencers grouped by activity
6. Manual add for non-club fencers

**Key Deliverable:** A single dashboard showing "where is everyone from my club right now?"

## 4. Code & Config (Entrypoints)
*Primary technical entrypoints for understanding the application's structure, dependencies, and configuration.*

- **Main Application:** `app/main.py` - FastAPI app with routes and handlers
- **Database:** `app/database.py` - SQLAlchemy setup (SQLite at `./fencer_schedules.db`)
- **Models:** `app/models.py` - User, UserSession, TrackedTournament, CachedEvent, TrackedFencer
- **Services:** `app/services/` - Business logic layer
  - `tournament_service.py` - Fencer status orchestration
  - `club_matcher.py` - Club matching logic
  - `auth_service.py` - Authentication
  - `rate_limit_service.py` - Rate limiting
- **FTL Module:** `app/ftl/` - Parsers, schemas, HTTP client
  - `parsers/tournament_schedule.py` - Extract events from tournament page
  - `parsers/event_rounds.py` - Extract pool/DE round IDs from event page
  - `parsers/pool_ids.py` - Extract pool IDs from event page
  - `parsers/pools.py` - Parse pool HTML
  - `parsers/pool_results.py` - Parse results JSON
  - `parsers/de_tableau.py` - Parse DE bracket HTML
  - `client.py` - HTTP client with retry/cache
  - `schemas.py` - Pydantic models
- **Auth:** `app/api/auth.py`, `app/services/` - Authentication system
- **Templates:** `app/templates/` - Jinja2 templates
- **Static:** `app/static/` - CSS styles

## 5. Testing & Development
*Resources for testing and local development.*

- **Run All Tests:** `.venv/bin/pytest tests/`
- **FTL Parser Tests:** `.venv/bin/pytest tests/ftl/` (94 tests)
- **API Tests:** `.venv/bin/pytest tests/api/`
- **Web Tests:** `.venv/bin/pytest tests/web/`
- **Test Event Data:** Sample artifacts in `comms/ftl_research_human*.md`
- **Test Tournament:** Capital Clash - `https://www.fencingtimelive.com/tournaments/eventSchedule/BBA4B7FACC464C93BA534ACE381A6C46`

## 6. Existing Assets (Reusable)

| Component | Status | Notes |
|-----------|--------|-------|
| FTL Parsers | ✅ Complete | Pool IDs, pools, results, DE tableau |
| HTTP Client | ✅ Complete | Retry, cache, bulk fetch |
| Auth System | ✅ Complete | Register, login, sessions, CSRF |
| Base Templates | ✅ Complete | Jinja2, Pico CSS |
| Detail Pages | ✅ Complete | /search, /pools, /advancement, /de |

## 7. New Work Required

| Component | Status | Notes |
|-----------|--------|-------|
| Tournament Parser | ✅ Complete | Parse schedule page |
| Event Round Discovery | ✅ Complete | Find pool/DE round IDs |
| User Profile (club) | ✅ Complete | Add club field |
| TrackedTournament model | ✅ Complete | Store user's tournaments |
| Dashboard UI | ✅ Complete | Consolidated fencer view |
| Manual Fencer Add | ✅ Complete | Cross-event search |
| Phase F Polish & Cleanup | ✅ Complete | Auto-cleanup, legacy removal |
| Phase I-K Visual Polish | ✅ Complete | High fidelity styling, mobile-first cards |
| Phase L Smart Caching | ✅ Complete | Optimization: skip fetching completed events |
| Deployment Prep | ✅ Complete | Procfile, Requirements, DB config for Cloud |

---

## Quick Start for AI Agents

**On session start:**
1. Read `comms/log.md` for recent activity
2. Read `comms/NEXT_STEPS.md` for current priorities
3. Read `comms/plan.md` for project vision and phases
4. Check `comms/tasks/` for any active spec

**Current Priority:** Phase I - Visual Polish

**Key Question to Answer:** How can we make the dashboard more dense and scan-friendly?

---

## File Organization Conventions

### `/comms/` - Communication & Planning
- `log.md` - Activity log
- `plan.md` - Development plan
- `NEXT_STEPS.md` - Immediate action items
- `roles/` - AI agent role definitions
- `tasks/` - Task specifications
- `tasks/archive/` - Completed specs
- `ftl_research*.md` - FTL sample data artifacts

### `/docs/` - Documentation
- `ARCHITECTURE.md` - System architecture
- `ftl-api-specification.md` - FTL parsing guide

### `/app/` - Source Code
- `main.py` - FastAPI application
- `database.py`, `models.py`, `crud.py` - Data layer
- `api/` - Route handlers
- `services/` - Business logic
- `ftl/` - FencingTimeLive integration
- `templates/`, `static/` - UI assets

### `/tests/` - Test Suite
- `ftl/` - Parser and client tests
- `api/` - API tests
- `web/` - Web UI tests

---

*This manifest is the single source of truth for project orientation. Keep it current.*
