"""Cleanup service for archiving stale tournaments."""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import CachedEvent, TrackedFencer, TrackedTournament


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def cleanup_expired_tournaments(db: Session, now: datetime, ttl_hours: int) -> int:
    """Archive tournaments older than TTL."""
    cutoff = now - timedelta(hours=ttl_hours)
    tournaments = (
        db.query(TrackedTournament)
        .filter(TrackedTournament.archived_at.is_(None))
        .all()
    )

    archived_count = 0
    for tournament in tournaments:
        last_access = tournament.last_accessed_at or tournament.created_at
        if last_access and _ensure_aware(last_access) < cutoff:
            db.query(CachedEvent).filter(
                CachedEvent.tracked_tournament_id == tournament.id
            ).delete(synchronize_session=False)
            db.query(TrackedFencer).filter(
                TrackedFencer.tracked_tournament_id == tournament.id
            ).delete(synchronize_session=False)
            tournament.archived_at = now
            archived_count += 1

    return archived_count


def touch_tournament_access(db: Session, tournament: TrackedTournament, now: datetime) -> None:
    """Update last_accessed_at for access tracking."""
    tournament.last_accessed_at = now
