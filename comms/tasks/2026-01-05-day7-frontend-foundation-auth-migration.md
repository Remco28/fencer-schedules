# Task: Day 7 — Frontend Foundation & Auth Migration
**Date:** 2026-01-05  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Establish a minimal web UI layer in `app/` (templates + static assets) and migrate core authentication from `project_kickstart/` into the active codebase. The result is a usable login/register flow and a basic dashboard page that will later host live tracking features, while keeping existing FTL API endpoints intact.

## User Stories
- As a new user, I can register with username, email, and password.
- As a returning user, I can log in and see a simple dashboard.
- As an authenticated user, I can log out securely.
- As a developer, I can keep using the existing `/api/*` endpoints without breaking tests.

## Scope (In)
- Create `app/templates/` and `app/static/` (new UI foundation).
- Serve Jinja2 templates and static files from the main FastAPI app.
- Migrate core auth models/services/routes from `project_kickstart/` into `app/`:
  - Models: `User`, `UserSession` (SQLAlchemy, using `app.database.Base`).
  - CRUD helpers for users/sessions.
  - Auth service with password hashing + session creation.
  - CSRF helpers and in-memory rate limiting.
  - Auth routes: register, login, logout, and `/auth/me`.
- Add a simple dashboard page at `/dashboard` (placeholder for future live tracking UI).
- Keep existing API routes and behavior unchanged (`/api/*` + `root()` health check).

## Scope (Out)
- Admin UI and user management.
- Tracked clubs/fencers UI.
- Email notifications (Mailgun) or background jobs.
- OAuth or third-party auth providers.
- Any data persistence beyond the local SQLite file.

## Deliverables
1. **Template + Static Setup**
   - `app/templates/base.html` (app layout + nav).
   - `app/templates/login.html`, `app/templates/register.html`, `app/templates/dashboard.html`.
   - `app/static/styles.css` (light styling; can reuse Pico CDN in base template if desired).
2. **Auth Models & Services**
   - `app/models.py` with `User` and `UserSession`.
   - `app/crud.py` with user/session CRUD helpers.
   - `app/services/auth_service.py`, `app/services/csrf_service.py`, `app/services/rate_limit_service.py`.
3. **Auth Routes + Dependencies**
   - `app/api/auth.py` (or `app/web/auth.py`) for register/login/logout/me.
   - `app/api/dependencies.py` (or `app/web/dependencies.py`) for session/CSRF helpers.
4. **Main App Wiring**
   - Update `app/main.py` to mount templates + static, include auth router, and add `/dashboard`.
   - Preserve existing API functions and tests (keep `root()` as health check).
5. **Tests**
   - Add new tests for auth flows (`tests/web/test_auth.py` or similar).
   - Existing `tests/api/*` and `tests/ftl/*` must remain green.

## Implementation Notes
- **Source of truth:** Reuse logic from:
  - `project_kickstart/app/models.py` (User, UserSession only)
  - `project_kickstart/app/crud.py` (user/session helpers only)
  - `project_kickstart/app/services/auth_service.py`
  - `project_kickstart/app/services/csrf_service.py`
  - `project_kickstart/app/services/rate_limit_service.py`
  - `project_kickstart/app/api/auth.py`
  - `project_kickstart/app/api/dependencies.py`
- **Email notifications:** Remove or no-op the `notify_admin_new_user` path so Mailgun deps are not required.
- **Database:** Update `app/database.py:init_db()` to import `app.models` in addition to `app.ftl.models`.
- **Routes:**
  - `GET /register` → render register page
  - `POST /auth/register` → create user, set cookie if desired, or redirect to login with `?registered=1`
  - `GET /login` → render login page
  - `POST /auth/login` → set session cookie on success
  - `POST /auth/logout` → invalidate session + clear cookie (CSRF protected)
  - `GET /dashboard` → requires auth; render placeholder UI
  - `GET /auth/me` → JSON for current user
- **Session cookie:**
  - Cookie name: `session_token`
  - HttpOnly, SameSite=Lax, Secure flag via `SESSION_COOKIE_SECURE` env var
- **CSRF:** Use the existing CSRF token helper for state-changing form posts.
- **Templates:** Keep base template minimal; update nav to only include Dashboard + Login/Register. Avoid legacy links (clubs/fencers/admin).
- **API health:** Leave the existing `root()` JSON response in `app/main.py` unchanged to keep `tests/api/test_api.py` passing.

## Testing Requirements
- Add a TestClient-based suite for:
  - Successful register → user row exists.
  - Login sets cookie and redirects (or returns JSON).
  - Logout clears cookie and invalidates session.
  - Accessing `/dashboard` without auth redirects to `/login` (or returns 401).
- Use a temporary SQLite DB and override `get_db` dependency for tests.

## Acceptance Criteria
- UI scaffold exists (`app/templates`, `app/static`).
- Register/login/logout flows work end-to-end via browser.
- Dashboard renders for authenticated users.
- No breaking changes to existing FTL API endpoints or tests.
- New auth tests pass; existing test suites remain green.
