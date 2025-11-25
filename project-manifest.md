# Project Manifest: Fencer Schedules App

**Purpose:** This file acts as a "map" for AI coding agents. It provides a stable set of pointers to critical project documentation and context, allowing the AI to quickly orient itself at the start of a new session.

**Last Updated:** 2025-11-20

---

## 1. Core Identity (Stable)
*These files define the project's high-level architecture, goals, and the roles of the participants. They should change infrequently.*

- **Architecture:** `docs/ARCHITECTURE.md`
- **Development Plan:** `comms/plan.md` - Phased rollout plan with Phase 1 (MVP) and Phase 2 (Live Tracking)
- **FTL API Specification:** `docs/ftl-api-specification.md` - Complete technical specification for FencingTimeLive scraper (15,000+ words)
- **Agent Roles:** `comms/roles/TECHADVISOR.md` - AI Technical Advisor role definition

## 2. Dynamic State (Volatile)
*These files and directories reflect the current status, recent work, and active tasks. The AI should check these to understand what's happening right now.*

- **Activity Log:** `comms/log.md` - Chronological record of major development activities
- **Current Next Steps:** `comms/NEXT_STEPS.md` - Immediate action items and priorities
- **Session Summaries:** `comms/SESSION_SUMMARY_*.md` - Detailed session notes (e.g., `SESSION_SUMMARY_2025-11-20.md`)
- **Active Research:** `comms/ftl_research_summary.md` - Executive summary of FTL scraping research

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
*These are the primary technical entrypoints for understanding the application's structure, dependencies, and configuration.*

**Note:** As of 2025-11-20, implementation has not yet begun. These will be created during Phase 1 and Phase 2 development.

**Planned Structure:**
- **Main Application:** TBD (will be Python-based backend + mobile-first frontend)
- **Scraper Service:** TBD (will be in `scraper_service/` or `backend/scraper/`)
- **Dependencies:** TBD (`requirements.txt` for Python backend)
- **Database Schema:** TBD (SQLite or PostgreSQL)
- **API Routes:** TBD (FastAPI or Flask)

## 5. Testing & Development
*Resources for testing and local development.*

- **Test Event Data:** See FTL sample files in `comms/ftl_research_human*.md`
- **Test URLs:** November NAC 2025 - Div I Men's Épée
  - Event ID: `54B9EF9A9707492E93F1D1F46CF715A2`
  - Pool Round ID: `D6890CA440324D9E8D594D5682CC33B7`
  - DE Round ID: `08DE5802C0F34ABEBBB468A9681713E7`

---

## Quick Start for AI Agents

**On session start:**
1. Read `comms/log.md` for recent activity
2. Read `comms/NEXT_STEPS.md` for current priorities
3. Review `comms/plan.md` for overall project status
4. If implementing FTL scraper: Read `docs/ftl-api-specification.md`

**Current Phase:** Research Complete - Ready for Implementation (Phase 2)

**Current Priority:** Begin scraper implementation (parsers, HTTP client, caching)

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

### `/src/` or `/backend/` - Source Code (Not Yet Created)
Future location for application code

### `/tests/` - Test Suite (Not Yet Created)
Future location for unit and integration tests

---

## Notes for Future Sessions

- **Phase 1 Status:** Not started (Core Schedule MVP without live tracking)
- **Phase 2 Status:** Research complete ✅, Implementation ready to begin
- **Key Decision:** Use Python for scraper (BeautifulSoup for HTML parsing, requests for HTTP)
- **Architecture Decision:** Parallel fetching (ThreadPoolExecutor) + aggressive caching (3-5 min TTL)
- **Risk Level:** LOW-MEDIUM (acceptable for MVP)
