"""Tests for user profile page."""
import os
import re
import tempfile

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


def _get_csrf_token(client) -> str:
    """Get CSRF token by fetching the profile page."""
    response = client.get("/profile")
    return _extract_csrf_token(response.text)


def test_profile_requires_auth(client):
    """GET /profile returns 401 without auth."""
    response = client.get("/profile")
    assert response.status_code == 401


def test_profile_renders(authenticated_client):
    """GET /profile renders for authenticated user."""
    response = authenticated_client.get("/profile")
    assert response.status_code == 200
    assert "Your Profile" in response.text
    assert "testuser" in response.text


def test_profile_update_club(authenticated_client):
    """POST /profile updates club field."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/profile",
        data={
            "csrf_token": csrf_token,
            "username": "testuser",
            "email": "test@example.com",
            "club": "Elite Fencers Club",
        },
    )
    assert response.status_code == 200
    assert "updated successfully" in response.text.lower()
    assert "Elite Fencers Club" in response.text


def test_profile_update_username(authenticated_client):
    """POST /profile can update username."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/profile",
        data={
            "csrf_token": csrf_token,
            "username": "newusername",
            "email": "test@example.com",
            "club": "",
        },
    )
    assert response.status_code == 200
    assert "newusername" in response.text


def test_profile_validates_empty_username(authenticated_client):
    """POST /profile rejects empty username."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/profile",
        data={
            "csrf_token": csrf_token,
            "username": "",
            "email": "test@example.com",
            "club": "",
        },
    )
    assert response.status_code == 200
    assert "required" in response.text.lower() or "error" in response.text.lower()


def test_profile_validates_duplicate_username(authenticated_client):
    """POST /profile rejects duplicate username."""
    authenticated_client.post(
        "/auth/register",
        data={
            "username": "otheruser",
            "email": "other@example.com",
            "password": "password123",
        },
    )

    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/profile",
        data={
            "csrf_token": csrf_token,
            "username": "otheruser",
            "email": "test@example.com",
            "club": "",
        },
    )
    assert response.status_code == 200
    assert "already exists" in response.text.lower()


def test_profile_requires_csrf(authenticated_client):
    """POST /profile requires CSRF token."""
    response = authenticated_client.post(
        "/profile",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "club": "Test Club",
        },
    )
    assert response.status_code == 403


def test_profile_club_optional(authenticated_client):
    """Club field can be empty."""
    csrf_token = _get_csrf_token(authenticated_client)
    response = authenticated_client.post(
        "/profile",
        data={
            "csrf_token": csrf_token,
            "username": "testuser",
            "email": "test@example.com",
            "club": "",
        },
    )
    assert response.status_code == 200
    assert "updated successfully" in response.text.lower()
