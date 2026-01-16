"""Tests for tournament setup flow."""
import os
import re
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import CachedEvent, TrackedTournament
from app.services import rate_limit_service


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limits before each test."""
    rate_limit_service._rate_limits.clear()
    yield
    rate_limit_service._rate_limits.clear()


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield engine, TestingSessionLocal

    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client):
    """Create a test client with authenticated session."""
    client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )

    session_token = login_response.cookies.get("session_token")
    client.cookies.set("session_token", session_token)

    return client


def _extract_csrf_token(html: str) -> str:
    """Extract CSRF token from HTML form."""
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    return ""


def test_tournament_new_requires_auth(client):
    """GET /tournament/new requires authentication."""
    response = client.get("/tournament/new")
    assert response.status_code == 401


def test_tournament_new_renders(authenticated_client):
    """GET /tournament/new renders for authenticated user."""
    response = authenticated_client.get("/tournament/new")
    assert response.status_code == 200
    assert "Track a Tournament" in response.text


def test_tournament_new_invalid_url(authenticated_client):
    """POST /tournament/new rejects invalid URL."""
    csrf_token = _extract_csrf_token(authenticated_client.get("/tournament/new").text)
    response = authenticated_client.post(
        "/tournament/new",
        data={
            "csrf_token": csrf_token,
            "url": "not-a-url",
            "club": "",
            "weapon": "",
        },
    )
    assert response.status_code == 200
    assert "valid FencingTimeLive tournament URL" in response.text


def test_tournament_new_creates_records(authenticated_client, test_db):
    """POST /tournament/new creates tracked tournament and cached events."""
    csrf_token = _extract_csrf_token(authenticated_client.get("/tournament/new").text)

    schedule = {
        "tournament_name": "Sample Tournament",
        "events": [
            {
                "event_id": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "name": "Senior Men's Epee",
                "date": "Jan 15, 2026",
                "start_time": "08:00 AM",
                "weapon": "Epee",
                "status": "Scheduled",
            }
        ],
    }

    with patch("app.main.fetch_tournament_schedule", return_value="<html></html>"), \
        patch("app.main.parse_tournament_schedule", return_value=schedule), \
        patch("app.main.fetch_event_page", return_value="<html></html>"), \
        patch("app.main.parse_event_rounds", return_value={
            "pool_round_id": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "de_round_id": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        }), \
        patch("app.main.fetch_competitors_json", return_value=[
            {"club1": "Elite Fencers Club", "club2": "", "clubNames": ""},
            {"club1": "Other Club", "club2": "", "clubNames": ""},
        ]):
        response = authenticated_client.post(
            "/tournament/new",
            data={
                "csrf_token": csrf_token,
                "url": "https://www.fencingtimelive.com/tournaments/eventSchedule/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "club": "Elite Fencers",
                "weapon": "Epee",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/tournament/")

    _, SessionLocal = test_db
    db = SessionLocal()
    try:
        tournaments = db.query(TrackedTournament).all()
        events = db.query(CachedEvent).all()
        assert len(tournaments) == 1
        assert len(events) == 1
        assert events[0].fencer_count == 1
    finally:
        db.close()


def test_tournament_detail_requires_auth(client, test_db):
    """GET /tournament/{id} requires authentication."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        tournament_name="Sample Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    db.close()

    response = client.get(f"/tournament/{tournament.id}")
    assert response.status_code == 401


def test_tournament_detail_renders(authenticated_client, test_db):
    """GET /tournament/{id} renders event list."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        tournament_name="Sample Tournament",
        tournament_url="https://example.com",
        club_filter="Elite Fencers",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    event = CachedEvent(
        tracked_tournament_id=tournament.id,
        event_id="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        event_name="Senior Men's Epee",
        fencer_count=2,
    )
    db.add(event)
    db.commit()
    tournament_id = tournament.id  # Save before closing session
    db.close()

    response = authenticated_client.get(f"/tournament/{tournament_id}")
    assert response.status_code == 200
    assert "Sample Tournament" in response.text
    assert "Senior Men" in response.text and "Epee" in response.text


def test_tournament_delete_requires_csrf(authenticated_client, test_db):
    """POST /tournament/{id}/delete requires CSRF token."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        tournament_name="Sample Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    db.close()

    response = authenticated_client.post(f"/tournament/{tournament.id}/delete")
    assert response.status_code == 403


def test_tournament_delete_removes_records(authenticated_client, test_db):
    """POST /tournament/{id}/delete removes records."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        tournament_name="Sample Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    event = CachedEvent(
        tracked_tournament_id=tournament.id,
        event_id="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        event_name="Senior Men's Epee",
    )
    db.add(event)
    db.commit()
    tournament_id = tournament.id  # Save before closing session
    db.close()

    detail_response = authenticated_client.get(f"/tournament/{tournament_id}")
    csrf_token = _extract_csrf_token(detail_response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/delete",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    db = SessionLocal()
    try:
        assert db.query(TrackedTournament).count() == 0
        assert db.query(CachedEvent).count() == 0
    finally:
        db.close()


def test_dashboard_shows_tournaments(authenticated_client, test_db):
    """Dashboard lists tracked tournaments."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        tournament_name="Sample Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.close()

    response = authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Sample Tournament" in response.text
