"""Tests for DE tableau page."""
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


def _get_csrf_token(client) -> str:
    """Get CSRF token by fetching the DE tableau page."""
    response = client.get("/de")
    return _extract_csrf_token(response.text)


def test_de_page_requires_auth(client):
    """Test that DE page requires authentication."""
    response = client.get("/de")
    assert response.status_code == 401


def test_de_page_renders_for_authenticated_user(authenticated_client):
    """Test that DE page renders for authenticated users."""
    response = authenticated_client.get("/de")

    assert response.status_code == 200
    assert "DE Tableau" in response.text
    assert "Event ID" in response.text
    assert "DE Round ID" in response.text


def test_de_submit_requires_auth(client):
    """Test that DE submit requires authentication."""
    response = client.post(
        "/de",
        data={
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        },
    )
    assert response.status_code == 401


def test_de_validates_empty_fields(authenticated_client):
    """Test that DE validates empty fields."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/de",
        data={
            "csrf_token": csrf_token,
            "event_id": "",
            "round_id": "",
        },
    )

    assert response.status_code == 200
    assert "Both fields are required" in response.text


def test_de_validates_event_id_format(authenticated_client):
    """Test that DE validates event ID format."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/de",
        data={
            "csrf_token": csrf_token,
            "event_id": "invalid",
            "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        },
    )

    assert response.status_code == 200
    assert "Event ID must be a 32-character hex string" in response.text


def test_de_validates_round_id_format(authenticated_client):
    """Test that DE validates round ID format."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/de",
        data={
            "csrf_token": csrf_token,
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "round_id": "too-short",
        },
    )

    assert response.status_code == 200
    assert "DE Round ID must be a 32-character hex string" in response.text


def test_de_shows_results(authenticated_client):
    """Test that DE renders grouped results."""
    csrf_token = _get_csrf_token(authenticated_client)
    mock_results = {
        "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
        "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        "groups": [
            {
                "label": "Table of 32",
                "matches": [
                    {
                        "name_a": "Jane Doe",
                        "name_b": "Sam Smith",
                        "seed_a": 3,
                        "seed_b": 30,
                        "score_a": 15,
                        "score_b": 9,
                        "winner": "A",
                        "strip": "B7",
                        "time": "2:15 PM",
                    }
                ],
            }
        ],
    }

    with patch("app.main._do_de_tableau", return_value=mock_results):
        response = authenticated_client.post(
            "/de",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
            },
        )

    assert response.status_code == 200
    assert "Table of 32" in response.text
    assert "Jane Doe" in response.text
    assert "Sam Smith" in response.text
    assert "B7" in response.text
    assert "2:15 PM" in response.text
    assert "winner" in response.text


def test_de_shows_no_results_message(authenticated_client):
    """Test that DE shows no results message."""
    csrf_token = _get_csrf_token(authenticated_client)
    mock_results = {
        "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
        "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        "groups": [],
    }

    with patch("app.main._do_de_tableau", return_value=mock_results):
        response = authenticated_client.post(
            "/de",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
            },
        )

    assert response.status_code == 200
    assert "No matches found" in response.text


def test_de_handles_http_error(authenticated_client):
    """Test that DE handles HTTP errors gracefully."""
    from app.ftl.client import FTLHTTPError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_de_tableau", side_effect=FTLHTTPError("Connection failed")):
        response = authenticated_client.post(
            "/de",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
            },
        )

    assert response.status_code == 200
    assert "Unable to reach the tournament server" in response.text


def test_de_handles_timeout_error(authenticated_client):
    """Test that DE handles timeout errors gracefully."""
    from app.ftl.client import FTLHTTPError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_de_tableau", side_effect=FTLHTTPError("Request Timeout")):
        response = authenticated_client.post(
            "/de",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
            },
        )

    assert response.status_code == 200
    assert "timed out" in response.text


def test_de_handles_parse_error(authenticated_client):
    """Test that DE handles parse errors gracefully."""
    from app.ftl.client import FTLParseError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_de_tableau", side_effect=FTLParseError("Invalid HTML")):
        response = authenticated_client.post(
            "/de",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
            },
        )

    assert response.status_code == 200
    assert "Error parsing tableau data" in response.text


def test_de_preserves_form_values_on_error(authenticated_client):
    """Test that DE preserves form values on validation error."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/de",
        data={
            "csrf_token": csrf_token,
            "event_id": "invalid",
            "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        },
    )

    assert response.status_code == 200
    assert 'value="invalid"' in response.text
    assert 'value="08DE5802C0F34ABEBBB468A9681713E7"' in response.text


def test_de_submit_requires_csrf(authenticated_client):
    """Test that DE submit requires CSRF token."""
    response = authenticated_client.post(
        "/de",
        data={
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "round_id": "08DE5802C0F34ABEBBB468A9681713E7",
        },
    )
    assert response.status_code == 403
