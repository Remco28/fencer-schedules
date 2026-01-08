"""Tests for authentication flows."""
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.database import Base, get_db
from app.main import app
from app import models
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
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    # Create engine and tables
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Override get_db dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield engine, TestingSessionLocal

    # Cleanup
    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Create a test client."""
    return TestClient(app)


def test_register_success(client):
    """Test successful user registration."""
    response = client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )

    # Should redirect to login page
    assert response.status_code == 303
    assert response.headers["location"] == "/login?registered=1"


def test_register_duplicate_username(client):
    """Test registration with duplicate username."""
    # Create first user
    client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # Try to register with same username
    response = client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "other@example.com",
            "password": "password456",
        },
    )

    assert response.status_code == 400
    assert "Username already exists" in response.text


def test_register_short_password(client):
    """Test registration with too short password."""
    response = client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 400
    assert "at least 8 characters" in response.text


def test_login_success(client):
    """Test successful login."""
    # Register user first
    client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # Login
    response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
        follow_redirects=False,
    )

    # Should redirect to dashboard
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    # Should set session cookie
    assert "session_token" in response.cookies


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    # Register user first
    client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # Try to login with wrong password
    response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert "Invalid credentials" in response.text


def test_dashboard_requires_auth(client):
    """Test that dashboard requires authentication."""
    response = client.get("/dashboard")

    assert response.status_code == 401


def test_dashboard_with_auth(client):
    """Test dashboard access with authentication."""
    # Register and login
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

    # Get session cookie
    session_token = login_response.cookies.get("session_token")

    client.cookies.set("session_token", session_token)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "testuser" in response.text


def test_logout_requires_csrf(client):
    """Test that logout requires CSRF token."""
    # Register and login
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

    # Try to logout without CSRF token
    client.cookies.set("session_token", session_token)
    response = client.post(
        "/auth/logout",
        data={},
        follow_redirects=False,
    )

    # Should fail with 403 Forbidden
    assert response.status_code == 403


def test_auth_me_endpoint(client):
    """Test /auth/me endpoint."""
    # Register and login
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

    # Call /auth/me
    client.cookies.set("session_token", session_token)
    response = client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_admin"] is False


def test_register_json_api(client):
    """Test registration via JSON API."""
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_login_json_api(client):
    """Test login via JSON API."""
    # Register first
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # Login via JSON
    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "ok"
    assert "session_token" in response.cookies
