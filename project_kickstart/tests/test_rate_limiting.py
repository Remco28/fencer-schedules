"""Tests for rate limiting functionality."""

import pytest

try:
    import httpx  # type: ignore
    HAS_HTTPX = True
except ModuleNotFoundError:
    HAS_HTTPX = False

if HAS_HTTPX:
    from fastapi.testclient import TestClient

from app import crud
from app.database import get_db
from app.main import app
from app.services import auth_service, rate_limit_service

pytestmark = pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")


def _create_user(db_session, username: str = "ratelimit-user"):
    password_hash = auth_service.hash_password("test-password")
    user = crud.create_user(db_session, username, f"{username}@example.com", password_hash)
    db_session.commit()
    return user


def _get_db_override(db_session):
    def override():
        try:
            yield db_session
        finally:
            pass
    return override


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_login_rate_limit_allows_under_threshold(db_session, monkeypatch):
    """Login attempts under threshold should succeed."""
    # Set low limits for testing
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "60")

    user = _create_user(db_session, "login-test-user")
    app.dependency_overrides[get_db] = _get_db_override(db_session)

    try:
        with TestClient(app) as client:
            # First 4 failed attempts should be allowed
            for i in range(4):
                response = client.post(
                    "/auth/login",
                    data={"username": user.username, "password": "wrong-password"}
                )
                assert response.status_code == 401, f"Attempt {i+1} should return 401"

            # 5th attempt should still be allowed (limit is 5)
            response = client.post(
                "/auth/login",
                data={"username": user.username, "password": "wrong-password"}
            )
            assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        # Clean up rate limit state
        rate_limit_service.reset_rate_limit(f"login:{user.username}")


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_login_rate_limit_blocks_over_threshold(db_session, monkeypatch):
    """Login attempts over threshold should be blocked."""
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "60")

    user = _create_user(db_session, "blocked-user")
    app.dependency_overrides[get_db] = _get_db_override(db_session)

    try:
        with TestClient(app) as client:
            # First 5 attempts exhaust the limit
            for _ in range(5):
                client.post(
                    "/auth/login",
                    data={"username": user.username, "password": "wrong"}
                )

            # 6th attempt should be blocked
            response = client.post(
                "/auth/login",
                data={"username": user.username, "password": "wrong"}
            )
            assert response.status_code == 429
            assert "Too many login attempts" in response.text
            assert "Retry-After" in response.headers
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limit_service.reset_rate_limit(f"login:{user.username}")


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_login_rate_limit_resets_on_success(db_session, monkeypatch):
    """Successful login should reset the rate limit counter."""
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "3")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "60")

    user = _create_user(db_session, "reset-user")
    app.dependency_overrides[get_db] = _get_db_override(db_session)

    try:
        with TestClient(app) as client:
            # 2 failed attempts
            for _ in range(2):
                client.post(
                    "/auth/login",
                    data={"username": user.username, "password": "wrong"}
                )

            # Successful login should reset counter
            response = client.post(
                "/auth/login",
                data={"username": user.username, "password": "test-password"}
            )
            assert response.status_code == 303  # Redirect on success

            # Now we can make 3 more failed attempts
            for _ in range(3):
                response = client.post(
                    "/auth/login",
                    data={"username": user.username, "password": "wrong"}
                )
                assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limit_service.reset_rate_limit(f"login:{user.username}")


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_register_rate_limit_by_ip(db_session, monkeypatch):
    """Registration attempts from same IP should be rate limited."""
    monkeypatch.setenv("REGISTER_RATE_LIMIT_ATTEMPTS", "3")
    monkeypatch.setenv("REGISTER_RATE_LIMIT_WINDOW_SEC", "60")

    app.dependency_overrides[get_db] = _get_db_override(db_session)

    try:
        with TestClient(app) as client:
            # First 3 attempts succeed (or fail for other reasons)
            for i in range(3):
                response = client.post(
                    "/auth/register",
                    data={
                        "username": f"user{i}",
                        "email": f"user{i}@example.com",
                        "password": "password123"
                    }
                )
                # Should not be rate limited
                assert response.status_code != 429

            # 4th attempt should be blocked
            response = client.post(
                "/auth/register",
                data={
                    "username": "user4",
                    "email": "user4@example.com",
                    "password": "password123"
                }
            )
            assert response.status_code == 429
            assert "Too many registration attempts" in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        # Clean up - would normally use client IP, but TestClient uses testclient
        rate_limit_service.reset_rate_limit("register:testclient")


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_rate_limit_error_message_json(db_session, monkeypatch):
    """JSON requests should receive JSON error responses."""
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "60")

    user = _create_user(db_session, "json-user")
    app.dependency_overrides[get_db] = _get_db_override(db_session)

    try:
        with TestClient(app) as client:
            # Exhaust limit with JSON requests
            for _ in range(2):
                client.post(
                    "/auth/login",
                    json={"username": user.username, "password": "wrong"},
                    headers={"Content-Type": "application/json"}
                )

            # Next request should get JSON error
            response = client.post(
                "/auth/login",
                json={"username": user.username, "password": "wrong"},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 429
            data = response.json()
            assert "detail" in data
            assert "Too many login attempts" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limit_service.reset_rate_limit(f"login:{user.username}")


def test_rate_limit_service_sliding_window():
    """Rate limit service should use sliding window algorithm."""
    import time

    key = "test:sliding"
    max_attempts = 3
    window_sec = 2

    # Clean slate
    rate_limit_service.reset_rate_limit(key)

    # First 3 attempts succeed
    for i in range(3):
        allowed, remaining = rate_limit_service.check_rate_limit(key, max_attempts, window_sec)
        assert allowed, f"Attempt {i+1} should be allowed"

    # 4th attempt fails
    allowed, remaining = rate_limit_service.check_rate_limit(key, max_attempts, window_sec)
    assert not allowed, "4th attempt should be blocked"

    # Wait for window to expire
    time.sleep(2.1)

    # Should be allowed again after window expires
    allowed, remaining = rate_limit_service.check_rate_limit(key, max_attempts, window_sec)
    assert allowed, "Should be allowed after window expires"

    # Clean up
    rate_limit_service.reset_rate_limit(key)
