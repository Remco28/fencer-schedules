"""Tests for manual fencer tracking."""
import re
from unittest.mock import patch

import pytest

from app.models import TrackedFencer, TrackedTournament
from app.services import rate_limit_service
from tests.web.test_tournament import authenticated_client, client, test_db


@pytest.fixture(autouse=True)
def clear_rate_limits():
    rate_limit_service._rate_limits.clear()
    yield
    rate_limit_service._rate_limits.clear()


def _create_tournament(session_factory, user_id=1):
    db = session_factory()
    tournament = TrackedTournament(
        user_id=user_id,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
        club_filter="Elite Fencers",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()
    return tournament_id


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def test_search_page_requires_auth(client, test_db):
    """Search page requires authentication."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)
    response = client.get(f"/tournament/{tournament_id}/search")
    assert response.status_code == 401


def test_search_page_renders(authenticated_client, test_db):
    """Search page renders for authenticated users."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)
    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    assert response.status_code == 200
    assert "Search Fencers" in response.text


def test_search_with_query(authenticated_client, test_db):
    """Search returns results for valid query."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    with patch("app.services.tournament_service.search_tournament_fencers", return_value=[
        {
            "name": "John Smith",
            "event_id": "B" * 32,
            "event_name": "Men's Epee",
            "club": "Other Club",
            "is_tracked": False,
        },
    ]):
        response = authenticated_client.get(f"/tournament/{tournament_id}/search?q=Smith")

    assert response.status_code == 200
    assert "John Smith" in response.text
    assert "Men" in response.text


def test_add_tracked_fencer(authenticated_client, test_db):
    """Can add a fencer to tracking list."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    csrf_token = _extract_csrf(response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/track",
        data={
            "csrf_token": csrf_token,
            "fencer_name": "Jane Doe",
            "redirect_url": f"/tournament/{tournament_id}/dashboard",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db = SessionLocal()
    fencer = db.query(TrackedFencer).filter(
        TrackedFencer.tracked_tournament_id == tournament_id,
        TrackedFencer.fencer_name == "Jane Doe",
    ).first()
    assert fencer is not None
    assert fencer.source == "manual"
    db.close()


def test_remove_tracked_fencer(authenticated_client, test_db):
    """Can remove a tracked fencer."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    db = SessionLocal()
    fencer = TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name="Jane Doe",
        source="manual",
    )
    db.add(fencer)
    db.commit()
    fencer_id = fencer.id
    db.close()

    response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")
    csrf_token = _extract_csrf(response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/untrack/{fencer_id}",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303

    db = SessionLocal()
    fencer = db.query(TrackedFencer).filter(TrackedFencer.id == fencer_id).first()
    assert fencer is None
    db.close()


def test_cannot_add_duplicate_fencer(authenticated_client, test_db):
    """Adding same fencer twice doesn't create duplicate."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    db = SessionLocal()
    fencer = TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name="Jane Doe",
        source="manual",
    )
    db.add(fencer)
    db.commit()
    db.close()

    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    csrf_token = _extract_csrf(response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/track",
        data={
            "csrf_token": csrf_token,
            "fencer_name": "Jane Doe",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db = SessionLocal()
    count = db.query(TrackedFencer).filter(
        TrackedFencer.tracked_tournament_id == tournament_id,
        TrackedFencer.fencer_name == "Jane Doe",
    ).count()
    assert count == 1
    db.close()
