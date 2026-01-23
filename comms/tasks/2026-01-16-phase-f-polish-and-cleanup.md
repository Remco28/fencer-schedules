# Task: Phase F — Polish & Cleanup (TTL Archive on Request)

**Date:** 2026-01-16
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Add an on-request TTL cleanup system that archives stale tournaments while preserving direct links. The system should reduce DB bloat by deleting cached event data and manual tracked fencers after a TTL, but keep the `TrackedTournament` record so links remain valid and can be restored.

## User Stories

- As a user, old tournaments are automatically cleaned up without me managing them.
- As a user, I can still open an old tournament link and restore it.
- As a user, I understand when a tournament is archived and how to reactivate it.

## Scope (In)

- On-request TTL cleanup (no scheduler).
- Soft-archive model for stale tournaments.
- Restore flow that rebuilds cached data.
- Light UI messaging for archived tournaments.
- Tests for cleanup + restore flow.

## Scope (Out)

- Background scheduler / cron.
- Permanent deletion without link preservation.
- New admin tools or analytics.

## Design Summary

- **On-request cleanup** runs during user navigation (e.g., `/dashboard`).
- **Soft-archive** old tournaments: mark as archived and delete heavy child data (`CachedEvent`, `TrackedFencer`).
- **Restore** re-runs tournament discovery to rebuild events and caches.

## Data Model Changes

Modify `TrackedTournament` in `app/models.py`:

```python
class TrackedTournament(Base):
    # ... existing fields ...
    last_accessed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
```

Behavior notes:
- `last_accessed_at` is updated on read access to tournament pages.
- `archived_at` is set when TTL expires and cleanup runs.
- Archived tournaments remain visible in dashboard but are flagged.

## Cleanup Policy

- TTL source: `last_accessed_at` (fallback to `created_at` if null).
- TTL duration: env var `TOURNAMENT_TTL_HOURS` (default 48).
- Cleanup trigger: on-request when a user loads `/dashboard`.

## Services / Logic

Create `app/services/cleanup_service.py` with:

```python
def cleanup_expired_tournaments(db: Session, now: datetime, ttl_hours: int) -> int:
    """Archive tournaments older than TTL.

    - Identify tournaments where last_accessed_at (or created_at) < now - ttl.
    - For each: delete CachedEvent + TrackedFencer rows; set archived_at.
    - Return count archived.
    """
```

Add helper:

```python
def touch_tournament_access(db: Session, tournament: TrackedTournament, now: datetime) -> None:
    """Update last_accessed_at for access tracking."""
```

Update access points to call `touch_tournament_access`:
- `GET /dashboard`
- `GET /tournament/{id}`
- `GET /tournament/{id}/dashboard`
- `GET /tournament/{id}/search`

## Restore Flow

Add a restore POST handler:

```
POST /tournament/{id}/restore
```

Behavior:
- If tournament is archived, rebuild events + club discovery using existing tournament setup flow.
- Clear `archived_at` and update `last_accessed_at`.
- Redirect to `/tournament/{id}/dashboard`.

This should reuse existing discovery logic (from Phase C) rather than duplicating logic.

## UI Updates

Update templates:

- `app/templates/dashboard.html`:
  - Show archived tournaments with a badge (e.g., “Archived”).
  - Provide a “Restore” button that posts to `/tournament/{id}/restore`.

- `app/templates/tournament_detail.html` and `app/templates/tournament_dashboard.html`:
  - If archived, show an info banner: “This tournament is archived. Restore to reload events.”
  - Disable event list if archived (no cached events).

## Tests

Add tests to `tests/web/`:

1. `test_cleanup_archives_old_tournaments`:
   - Create tournament with old `last_accessed_at` and children.
   - Hit `/dashboard`.
   - Assert `archived_at` set, child rows deleted.

2. `test_dashboard_shows_archived_badge`:
   - Create archived tournament.
   - Assert dashboard shows “Archived” and restore form.

3. `test_restore_rebuilds_events`:
   - Create archived tournament with no events.
   - Mock tournament schedule + event discovery; POST restore.
   - Assert events are re-created and `archived_at` cleared.

4. `test_restore_requires_auth`:
   - Ensure restore endpoint is protected.

## Acceptance Criteria

- [ ] Old tournaments are archived on request using TTL policy.
- [ ] Archived tournaments retain links and can be restored.
- [ ] Archived tournaments delete `CachedEvent` and `TrackedFencer` data.
- [ ] UI clearly shows archived status and restore action.
- [ ] Tests cover cleanup + restore flows.
- [ ] No regressions in existing tournament flows.

## Files to Create/Modify

**Create:**
- `app/services/cleanup_service.py`

**Modify:**
- `app/models.py` (add `last_accessed_at`, `archived_at`)
- `app/main.py` (invoke cleanup, touch access, add restore route)
- `app/templates/dashboard.html` (archived badge + restore)
- `app/templates/tournament_detail.html` (archived banner)
- `app/templates/tournament_dashboard.html` (archived banner)
- `tests/web/` (new TTL/restore tests)

