# Project Manifest: Fencer Schedules App

**Purpose:** This file acts as a "map" for AI coding agents. It provides a stable set of pointers to critical project documentation and context, allowing the AI to quickly orient itself at the start of a new session.

**Last Updated:** 2025-11-26

---

## 1. Core Identity (Stable)
*These files define the project's high-level architecture, goals, and the roles of the participants. They should change infrequently.*

- **Architecture:** `docs/ARCHITECTURE.md`
- **Development Plan:** `comms/plan.md` - Phased rollout plan with Phase 1 (MVP) and Phase 2 (Live Tracking)
- **FTL API Specification:** `docs/ftl-api-specification.md` - Complete technical specification for FencingTimeLive scraper (15,000+ words)
- **Agent Roles:** `comms/roles/ARCHITECT.md`, `comms/roles/TECHADVISOR.md`

## 2. Dynamic State (Volatile)
*These files and directories reflect the current status, recent work, and active tasks. The AI should check these to understand what's happening right now.*

- **Activity Log:** `comms/log.md` - Chronological record of major development activities
- **Current Next Steps:** `comms/NEXT_STEPS.md` - Immediate action items and priorities
- **Session Summaries:** `comms/SESSION_SUMMARY_*.md` - Detailed session notes (e.g., `SESSION_SUMMARY_2025-11-20.md`)
- **Active Research:** `comms/ftl_research_summary.md` - Executive summary of FTL scraping research
- **Code Location (active):** `app/` at repo root (new FTL parsers and database)
- **Legacy Reference:** `project_kickstart/` (temporary scaffold; planned removal after extraction)
- **Current Task Spec:** _None active_ (Day 6 complete; awaiting next spec)
- **Archived Task Specs:** `comms/tasks/archive/2025-11-25-ftl-day1-structure-and-pool-id-extractor.md`; `comms/tasks/archive/2025-11-25-ftl-day2-pool-html-parser.md`; `comms/tasks/archive/2025-11-26-ftl-day3-pool-results-json-parser.md`; `comms/tasks/archive/2025-11-26-ftl-day4-http-client-and-bulk-pool-fetch.md`; `comms/tasks/archive/2025-11-26-ftl-day5-de-tableau-parser.md`; `comms/tasks/archive/2025-11-26-ftl-day6-api-endpoints-and-integration.md`

## 3. Research & Documentation (Reference)
*Background research and detailed findings that inform implementation decisions.*

- **FTL Research Summary:** `comms/ftl_research_summary.md` - Quick reference for FencingTimeLive findings
- **FTL API Specification:** `docs/ftl-api-specification.md` - Complete scraper implementation guide
- **FTL Sample Data:**
  - `comms/ftl_research_human.md` - DE tableau HTML sample
  - `comms/ftl_research_human_pools.md` - Individual pool HTML sample
  - `comms/ftl_research_human_pools_results.md` - Pool results JSON sample
  - `comms/ftl_research_human_pool_ids.md` - Pool IDs JavaScript array sample

## 4. Code & Config (Entrypoints)
*Primary technical entrypoints for understanding the application's structure, dependencies, and configuration.*

- **Main Application:** `app/` (root) — Python backend; mobile-first frontend to be added in later phases.
- **FTL Module:** `app/ftl/` with parsers (`parsers/pool_ids.py`, `parsers/pools.py`, `parsers/pool_results.py`, `parsers/de_tableau.py`), schemas (`schemas.py`), models (`models.py`), and HTTP client (`client.py`).
- **Database Schema:** `app/database.py` (SQLite dev default at `./fencer_schedules.db`; imports SQLAlchemy `Base` and FTL models).
- **Tests:** `tests/ftl/` (94 passing tests: pool IDs, pool HTML, pool results, HTTP client, DE tableau); `tests/conftest.py` ensures repo root on `sys.path`.
- **Dependencies:** Use `.venv`; install `requests`, `beautifulsoup4`, `pydantic`, `pytest` (SQLAlchemy is required for database models and for running legacy kickstart tests).
- **Legacy Reference:** `project_kickstart/` — temporary FastAPI/Jinja scaffold for fencingtracker.com. Keep read-only; tests there require extra deps (e.g., SQLAlchemy) and are not part of the active Phase 2 work.

## 5. Testing & Development
*Resources for testing and local development.*

- **Active Tests:** Run `.venv/bin/pytest tests/ftl` (parsers + HTTP client) and `.venv/bin/pytest tests/api/test_api.py` (API handlers, patched fetches). Legacy `project_kickstart/tests` need extra deps (SQLAlchemy/typer); skip unless working on legacy code.
- **Test Event Data:** See FTL sample files in `comms/ftl_research_human*.md`
- **Test URLs:** November NAC 2025 - Div I Men's Épée
  - Event ID: `54B9EF9A9707492E93F1D1F46CF715A2`
  - Pool Round ID: `D6890CA440324D9E8D594D5682CC33B7`
  - DE Round ID: `08DE5802C0F34ABEBBB468A9681713E7`

---

## Quick Start for AI Agents

**On session start:**
1. Read `comms/log.md` for recent activity.
2. Read `comms/NEXT_STEPS.md` for current priorities (Phase 2 implementation).
3. Review `comms/plan.md` for overall project status.
4. If implementing FTL scraper: read `docs/ftl-api-specification.md`.
5. Run `.venv/bin/pytest tests/ftl` to verify parsers before/after changes.

**Current Phase:** Phase 2 Implementation (Week 1 complete: all core parsers + HTTP client done)

**Current Priority:** Day 5 complete. Next: Integration tests or API endpoints (Week 2).

---

## File Organization Conventions

### `/comms/` - Communication & Planning
- `log.md` - Activity log
- `plan.md` - Overall development plan
- `NEXT_STEPS.md` - Immediate action items
- `roles/` - AI agent role definitions
- `tasks/` - Task specifications (future use)
- `SESSION_SUMMARY_*.md` - Session notes
- `ftl_research*.md` - FencingTimeLive research artifacts

### `/docs/` - Documentation
- `ARCHITECTURE.md` - System architecture (future)
- `ftl-api-specification.md` - Complete FTL scraper spec
- `project-manifest.template.md` - Template for this file

### `/app/` - Source Code (Active)
Python application code (FTL parsers under `app/ftl/`, database at `app/database.py`)

### `/tests/` - Test Suite (Active)
Current tests for FTL parsers (`tests/ftl/`)

### `/project_kickstart/` - Legacy Reference
Temporary scaffold (FastAPI/Jinja/Auth/scraper for fencingtracker.com); keep read-only

---

## Notes for Future Sessions

- **Phase 1 Status:** Not started (Core Schedule MVP without live tracking)
- **Phase 2 Status:** Week 1 complete (all parsers + HTTP client implemented; 94 tests passing)
- **Key Decision:** Use Python for scraper (BeautifulSoup for HTML parsing, requests for HTTP)
- **Architecture Decision:** Parallel fetching (ThreadPoolExecutor) + aggressive caching (180s TTL)
- **Risk Level:** LOW-MEDIUM (acceptable for MVP)
