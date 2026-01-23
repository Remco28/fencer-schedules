"""Tests for tournament cleanup and restore."""
import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.models import CachedEvent, TrackedFencer, TrackedTournament
from tests.web.test_tournament import authenticated_client, client, test_db


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def _create_tournament(session_factory, user_id=1, archived=False):
    db = session_factory()
    tournament = TrackedTournament(
        user_id=user_id,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
        club_filter="Elite Fencers",
        last_accessed_at=datetime.now(UTC) - timedelta(hours=60),
        archived_at=datetime.now(UTC) if archived else None,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    db.close()
    return tournament.id


def test_cleanup_archives_old_tournaments(authenticated_client, test_db):
    """Old tournaments are archived and children removed on dashboard load."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    db = SessionLocal()
    db.add(CachedEvent(
        tracked_tournament_id=tournament_id,
        event_id="B" * 32,
        event_name="Sample Event",
    ))
    db.add(TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name="Jane Doe",
        source="manual",
    ))
    db.commit()
    db.close()

    response = authenticated_client.get("/dashboard")
    assert response.status_code == 200

    db = SessionLocal()
    try:
        tournament = db.query(TrackedTournament).filter(TrackedTournament.id == tournament_id).first()
        assert tournament.archived_at is not None
        assert db.query(CachedEvent).filter(CachedEvent.tracked_tournament_id == tournament_id).count() == 0
        assert db.query(TrackedFencer).filter(TrackedFencer.tracked_tournament_id == tournament_id).count() == 0
    finally:
        db.close()


def test_dashboard_shows_archived_badge(authenticated_client, test_db):
    """Dashboard shows archived badge and restore action."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal, archived=True)

    response = authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Archived" in response.text
    assert f"/tournament/{tournament_id}/restore" in response.text


def test_restore_rebuilds_events(authenticated_client, test_db):
    """Restore rebuilds cached events and clears archived flag."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal, archived=True)

    def _fake_build(db, tracked, force_refresh=False):
        db.add(CachedEvent(
            tracked_tournament_id=tracked.id,
            event_id="C" * 32,
            event_name="Restored Event",
        ))
        return 1

    response = authenticated_client.get("/dashboard")
    csrf_token = _extract_csrf(response.text)

    with patch("app.main._build_tournament_events", side_effect=_fake_build):
        response = authenticated_client.post(
            f"/tournament/{tournament_id}/restore",
            data={"csrf_token": csrf_token},
            follow_redirects=False,
        )

    assert response.status_code == 303

    db = SessionLocal()
    try:
        tournament = db.query(TrackedTournament).filter(TrackedTournament.id == tournament_id).first()
        assert tournament.archived_at is None
        assert db.query(CachedEvent).filter(CachedEvent.tracked_tournament_id == tournament_id).count() == 1
    finally:
        db.close()


def test_restore_requires_auth(client, test_db):
    """Restore endpoint requires authentication."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal, archived=True)

    response = client.post(f"/tournament/{tournament_id}/restore")
    assert response.status_code == 401
