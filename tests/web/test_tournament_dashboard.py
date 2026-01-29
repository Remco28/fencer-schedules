"""Tests for consolidated tournament dashboard."""
import pytest
from unittest.mock import patch

from app.models import TrackedTournament
from app.services.tournament_service import FencerStatus
from app.services import rate_limit_service
from tests.web.test_tournament import authenticated_client, client, test_db


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limits before each test."""
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
    tournament_id = tournament.id  # Save ID before closing
    db.close()
    return tournament_id


def test_dashboard_requires_auth(client, test_db):
    """Dashboard requires authentication."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    response = client.get(f"/tournament/{tournament_id}/dashboard")
    assert response.status_code == 401


def test_dashboard_renders(authenticated_client, test_db):
    """Dashboard renders with empty data."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    with patch("app.main.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Test Tournament" in response.text
    assert "Active Now" in response.text
    assert "Waiting" in response.text
    assert "Finished" in response.text


def test_dashboard_shows_active_fencers(authenticated_client, test_db):
    """Dashboard displays active fencers."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    active_fencer = FencerStatus(
        name="Jane Smith",
        event_id="B" * 32,
        event_name="Women's Epee",
        weapon="Epee",
        strip="A5",
        pool_number=3,
        activity="active",
        phase="pools",
    )

    with patch("app.main.get_tournament_fencer_status", return_value={
        "active": [active_fencer],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Jane Smith" in response.text
    assert "Women" in response.text and "Epee" in response.text
    # Card layout uses separate label and value elements
    assert "Strip" in response.text and "A5" in response.text
    assert "Pool" in response.text and ">3<" in response.text


def test_dashboard_shows_finished_fencers(authenticated_client, test_db):
    """Dashboard displays finished fencers with results."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    finished_fencer = FencerStatus(
        name="Bob Johnson",
        event_id="B" * 32,
        event_name="Men's Foil",
        weapon="Foil",
        activity="finished",
        phase="de",
        result="Eliminated (Table of 32)",
    )

    with patch("app.main.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [finished_fencer],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Bob Johnson" in response.text
    assert "Eliminated" in response.text


def test_dashboard_force_refresh(authenticated_client, test_db):
    """Dashboard accepts force_refresh parameter."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    with patch("app.main.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(
            f"/tournament/{tournament_id}/dashboard?force_refresh=true"
        )

    assert response.status_code == 200


def test_dashboard_handles_errors(authenticated_client, test_db):
    """Dashboard shows error message when fetch fails."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    with patch(
        "app.main.get_tournament_fencer_status",
        side_effect=Exception("Network error"),
    ):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Failed to fetch" in response.text or "Network error" in response.text
