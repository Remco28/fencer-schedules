"""Tests for fencer search page."""
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


def _extract_csrf_token(html: str) -> str:
    """Extract CSRF token from HTML form."""
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    return ""


@pytest.fixture
def authenticated_client(client):
    """Create a test client with authenticated session."""
    # Register user
    client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # Login
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


def _get_csrf_token(client) -> str:
    """Get CSRF token by fetching the search page."""
    response = client.get("/search")
    return _extract_csrf_token(response.text)


def test_search_page_requires_auth(client):
    """Test that search page requires authentication."""
    response = client.get("/search")
    assert response.status_code == 401


def test_search_page_renders_for_authenticated_user(authenticated_client):
    """Test that search page renders for authenticated users."""
    response = authenticated_client.get("/search")

    assert response.status_code == 200
    assert "Fencer Search" in response.text
    assert "Event ID" in response.text
    assert "Pool Round ID" in response.text
    assert "Fencer Name" in response.text


def test_search_submit_requires_auth(client):
    """Test that search submit requires authentication."""
    response = client.post(
        "/search",
        data={
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
            "name": "Smith",
        },
    )
    assert response.status_code == 401


def test_search_validates_empty_fields(authenticated_client):
    """Test that search validates empty fields."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/search",
        data={
            "csrf_token": csrf_token,
            "event_id": "",
            "pool_round_id": "",
            "name": "",
        },
    )

    assert response.status_code == 200
    assert "All fields are required" in response.text


def test_search_validates_event_id_format(authenticated_client):
    """Test that search validates event ID format."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/search",
        data={
            "csrf_token": csrf_token,
            "event_id": "invalid",
            "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
            "name": "Smith",
        },
    )

    assert response.status_code == 200
    assert "Event ID must be a 32-character hex string" in response.text


def test_search_validates_pool_round_id_format(authenticated_client):
    """Test that search validates pool round ID format."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/search",
        data={
            "csrf_token": csrf_token,
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "pool_round_id": "too-short",
            "name": "Smith",
        },
    )

    assert response.status_code == 200
    assert "Pool Round ID must be a 32-character hex string" in response.text


def test_search_shows_results(authenticated_client):
    """Test that search shows results."""
    csrf_token = _get_csrf_token(authenticated_client)
    mock_results = {
        "query": "Smith",
        "matches": [
            {
                "name": "John Smith",
                "pool_number": 5,
                "strip": "A3",
                "club": "Salle Boston",
                "status": "unknown",
                "source": "pool",
            },
        ],
    }

    with patch("app.main._do_fencer_search", return_value=mock_results):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Smith",
            },
        )

    assert response.status_code == 200
    assert "John Smith" in response.text
    assert "Salle Boston" in response.text
    assert "A3" in response.text
    assert "Found <strong>1</strong> match" in response.text


def test_search_shows_no_results_message(authenticated_client):
    """Test that search shows no results message."""
    csrf_token = _get_csrf_token(authenticated_client)
    mock_results = {
        "query": "Nobody",
        "matches": [],
    }

    with patch("app.main._do_fencer_search", return_value=mock_results):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Nobody",
            },
        )

    assert response.status_code == 200
    assert "No matches found" in response.text


def test_search_handles_http_error(authenticated_client):
    """Test that search handles HTTP errors gracefully."""
    from app.ftl.client import FTLHTTPError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_fencer_search", side_effect=FTLHTTPError("Connection failed")):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Smith",
            },
        )

    assert response.status_code == 200
    assert "Unable to reach the tournament server" in response.text


def test_search_handles_timeout_error(authenticated_client):
    """Test that search handles timeout errors gracefully."""
    from app.ftl.client import FTLHTTPError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_fencer_search", side_effect=FTLHTTPError("Request Timeout")):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Smith",
            },
        )

    assert response.status_code == 200
    assert "timed out" in response.text


def test_search_handles_parse_error(authenticated_client):
    """Test that search handles parse errors gracefully."""
    from app.ftl.client import FTLParseError

    csrf_token = _get_csrf_token(authenticated_client)
    with patch("app.main._do_fencer_search", side_effect=FTLParseError("Invalid HTML")):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Smith",
            },
        )

    assert response.status_code == 200
    assert "Error parsing tournament data" in response.text


def test_search_preserves_form_values_on_error(authenticated_client):
    """Test that search preserves form values on validation error."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/search",
        data={
            "csrf_token": csrf_token,
            "event_id": "invalid",
            "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
            "name": "Smith",
        },
    )

    assert response.status_code == 200
    # Form values should be preserved
    assert 'value="invalid"' in response.text
    assert 'value="D6890CA440324D9E8D594D5682CC33B7"' in response.text
    assert 'value="Smith"' in response.text


def test_search_displays_multiple_results(authenticated_client):
    """Test that search displays multiple results correctly."""
    csrf_token = _get_csrf_token(authenticated_client)
    mock_results = {
        "query": "Smith",
        "matches": [
            {
                "name": "John Smith",
                "pool_number": 5,
                "strip": "A3",
                "club": "Club A",
                "status": "unknown",
                "source": "pool",
            },
            {
                "name": "Jane Smith",
                "pool_number": None,
                "strip": None,
                "club": "Club B",
                "status": "advanced",
                "source": "results",
            },
            {
                "name": "Bob Smith",
                "pool_number": None,
                "strip": None,
                "club": "Club C",
                "status": "eliminated",
                "source": "results",
            },
        ],
    }

    with patch("app.main._do_fencer_search", return_value=mock_results):
        response = authenticated_client.post(
            "/search",
            data={
                "csrf_token": csrf_token,
                "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
                "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
                "name": "Smith",
            },
        )

    assert response.status_code == 200
    assert "Found <strong>3</strong> match" in response.text
    assert "John Smith" in response.text
    assert "Jane Smith" in response.text
    assert "Bob Smith" in response.text
    # Check status styling
    assert "status-advanced" in response.text
    assert "status-eliminated" in response.text


def test_search_submit_requires_csrf(authenticated_client):
    """Test that search submit requires CSRF token."""
    response = authenticated_client.post(
        "/search",
        data={
            "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
            "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
            "name": "Smith",
        },
    )
    # Should fail with 403 Forbidden due to missing CSRF
    assert response.status_code == 403
