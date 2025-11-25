# project_kickstart Review (2025-11-25)

## Quick Read
- Stack: FastAPI + Jinja2, Typer CLI, SQLAlchemy (SQLite), APScheduler, requests/BeautifulSoup scrapers, Mailgun notifications, PicoCSS templates.
- Purpose today: monitors fencingtracker.com club registrations; sends emails; users can track clubs/fencers with sessions, CSRF, rate limits.
- Tests: pytest suite covers auth, rate limiting, scraper services, fencer/club CRUD, CSRF, and an e2e tracked-fencer flow.

## What Exists
- Entry: `app/main.py` mounts routers, health, Typer commands (db init, scrape, schedule, digests, admin creation).
- Data model: `Tournament`, `Fencer`, `Registration` (unique per fencer+tournament, comma-separated events), `User`, `UserSession`, `TrackedClub`, `TrackedFencer`. Uses `Base.metadata.create_all` (Alembic stub present but unused).
- Services: fencingtracker club scraper (`scraper_service.py`), fencer profile scraper with throttling and change detection, digest email builder, CSRF tokens, rate limiting (in-memory dict), Mailgun client, validation helpers.
- Web: Jinja templates for dashboard + tracked clubs/fencers + auth; PicoCSS styling; cookies for session auth.
- Infra: APScheduler for recurring scrapes (club + fencer), dotenv loading, Mailgun integration hooks.

## Gaps vs Fencer Schedules Phase 2 (FTL live tracking)
- Domain mismatch: models capture club registrations, not event rounds/pools/strips/brackets; no place for FTL event IDs, pool IDs, tableau, or caching.
- Scraping targets fencingtracker HTML, not FencingTimeLive; no parallel fetcher, TTL cache, or JSON/HTML parsers described in `docs/ftl-api-specification.md`.
- Data storage: SQLite only and no migrations; event-scale data and schema changes would need new models/migrations.
- UI: dashboard focused on club/fencer registration tracking, not “where is my fencer?” live views.
- Concurrency/perf: services use blocking requests; no async or concurrency controls for high-volume pool fetches.

## Recommendation
- **Reuse the scaffold** (FastAPI/Jinja/Typer/auth/rate limits/CSRF/tests harness) to avoid rebuilding plumbing, but **isolate FTL work** in a new module (e.g., `app/ftl/` or `app/services/ftl_*`) with separate models/tables for events, pools, bouts, cache entries.
- Add real migrations (Alembic) before introducing new tables, or cordon new schema into its own SQLite/Postgres file to keep the legacy registration data optional.
- Plan a slim API layer for Phase 2 (read-only endpoints for pools/DEs) alongside existing auth/session middleware; templates can be new views under `/ftl/*` without touching current ones.
- Keep fencingtracker scrapers intact but optional; they don’t block Phase 2 but can coexist if namespaced.  

## Next Steps I suggest
1) Decide DB path (extend current SQLite with migrations vs new DB file/schema).  
2) Define FTL models and service layout (client, parsers, cache) aligned with `docs/ftl-api-specification.md`.  
3) Draft a task spec for Day 1: set up project structure + pool ID extractor + tests using sample artifacts.  
4) Update manifest/log once decision on reuse vs fresh is finalized.  
