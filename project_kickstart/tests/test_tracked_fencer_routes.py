from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

try:
    import httpx  # type: ignore
    HAS_HTTPX = True
except ModuleNotFoundError:
    HAS_HTTPX = False

if HAS_HTTPX:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")

from app import crud
from app.main import app
from app.database import get_db
from app.models import User
from app.services import auth_service
from app.api.dependencies import SESSION_COOKIE_NAME, get_current_user


def _override_db(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override


def _override_current_user(user: User):
    def _get_user_override():
        return user

    app.dependency_overrides[get_current_user] = _get_user_override


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@contextmanager
def _authenticated_client(db_session, user):
    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()
    session = crud.get_session(db_session, token)
    csrf_token = session.csrf_token if session else ""

    _override_db(db_session)
    _override_current_user(user)

    try:
        with TestClient(app) as client:
            client.cookies.set(SESSION_COOKIE_NAME, token)
            yield client, csrf_token
    finally:
        _clear_overrides()
def test_create_tracked_fencer_success(db_session):
    password_hash = auth_service.hash_password("example-password")
    user = crud.create_user(db_session, "fencer-user", "user@example.com", password_hash)
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://fencingtracker.com/p/12345/alex-foil",
                "weapon_filter": "foil,epee",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    tracked = crud.get_tracked_fencer_for_user(db_session, user.id, "12345")
    assert tracked is not None
    assert tracked.display_name == "Alex Foil"
    assert tracked.weapon_filter == "epee,foil"
    assert tracked.active is True


def test_create_tracked_fencer_accepts_profile_url(db_session):
    password_hash = auth_service.hash_password("profile-url-test")
    user = crud.create_user(db_session, "profile-user", "profile@example.com", password_hash)
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://www.fencingtracker.com/p/54321/olivia-s",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    assert "success=Fencer%20tracked%20successfully" in response.headers.get("location", "")
    tracked = crud.get_tracked_fencer_for_user(db_session, user.id, "54321")
    assert tracked is not None
    assert tracked.fencer_id == "54321"


def test_create_tracked_fencer_slug_auto_name(db_session):
    password_hash = auth_service.hash_password("slug-name-test")
    user = crud.create_user(db_session, "slug-user", "slug@example.com", password_hash)
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://www.fencingtracker.com/p/42424/mia-o-connor",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    tracked = crud.get_tracked_fencer_for_user(db_session, user.id, "42424")
    assert tracked is not None
    assert tracked.display_name == "Mia O Connor"


def test_create_tracked_fencer_slugless_uses_scraper_helper(monkeypatch, db_session):
    password_hash = auth_service.hash_password("slugless-name-test")
    user = crud.create_user(db_session, "slugless-user", "slugless@example.com", password_hash)
    db_session.commit()

    calls = []

    def _fake_fetch(fencer_id: str, timeout: float = 3.0):
        calls.append((fencer_id, timeout))
        return "Jordan Lee"

    from app.api import tracked_fencers as tracked_fencers_module

    monkeypatch.setattr(
        tracked_fencers_module.fencer_scraper_service,
        "fetch_fencer_display_name",
        _fake_fetch,
    )

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://fencingtracker.com/p/50505",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    tracked = crud.get_tracked_fencer_for_user(db_session, user.id, "50505")
    assert tracked is not None
    assert tracked.display_name == "Jordan Lee"
    assert calls and calls[0][0] == "50505"


def test_create_tracked_fencer_duplicate_error(db_session):
    password_hash = auth_service.hash_password("duplicate-test")
    user = crud.create_user(db_session, "dupe-user", "dupe@example.com", password_hash)
    crud.create_tracked_fencer(db_session, user.id, "777", display_name="First")
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "777",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 400
    assert "Fencer already tracked" in response.text


def test_create_tracked_fencer_reactivates_with_profile_url(db_session):
    password_hash = auth_service.hash_password("reactivate-url-test")
    user = crud.create_user(db_session, "reactivate-user", "reactivate@example.com", password_hash)
    tracked = crud.create_tracked_fencer(db_session, user.id, "13579", display_name="Dormant")
    tracked.active = False
    tracked.failure_count = 3
    tracked.last_failure_at = datetime.now(UTC)
    tracked.last_checked_at = datetime.now(UTC)
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://fencingtracker.com/p/13579/dormant",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    assert "success=Fencer%20re-activated" in response.headers.get("location", "")
    db_session.refresh(tracked)
    assert tracked.active is True
    assert tracked.failure_count == 0
    assert tracked.last_failure_at is None
    assert tracked.last_checked_at is None


def test_create_tracked_fencer_invalid_profile_url_error(db_session):
    password_hash = auth_service.hash_password("invalid-url-test")
    user = crud.create_user(db_session, "invalid-url-user", "invalid-url@example.com", password_hash)
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={
                "fencer_id": "https://www.fencingtracker.com/p/not-a-number",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 400
    assert "Could not find a numeric ID" in response.text


def test_edit_tracked_fencer_normalizes_weapon_filter(db_session):
    password_hash = auth_service.hash_password("edit-test")
    user = crud.create_user(db_session, "edit-user", "edit@example.com", password_hash)
    tracked = crud.create_tracked_fencer(db_session, user.id, "321", display_name="Casey")
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            f"/fencers/{tracked.id}/edit",
            data={
                "display_name": "Casey",
                "weapon_filter": "Saber, Foil, Saber",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 303
    db_session.refresh(tracked)
    assert tracked.weapon_filter == "foil,saber"


def test_deactivate_tracked_fencer(db_session):
    password_hash = auth_service.hash_password("deactivate-test")
    user = crud.create_user(db_session, "deactivate-user", "deactivate@example.com", password_hash)
    tracked = crud.create_tracked_fencer(db_session, user.id, "555", display_name="Taylor")
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            f"/fencers/{tracked.id}/deactivate",
            data={"csrf_token": csrf_token},
        )

    assert response.status_code == 303
    db_session.refresh(tracked)
    assert tracked.active is False
    active_only = crud.get_all_tracked_fencers_for_user(db_session, user.id, active_only=True)
    assert active_only == []

def test_get_tracked_fencers_dashboard(db_session):
    password_hash = auth_service.hash_password("dashboard-test")
    user = crud.create_user(db_session, "dashboard-user", "dashboard@example.com", password_hash)
    crud.create_tracked_fencer(db_session, user.id, "111", display_name="Fencer One")
    crud.create_tracked_fencer(db_session, user.id, "222", display_name="Fencer Two", weapon_filter="saber")
    db_session.commit()

    with _authenticated_client(db_session, user) as (client, _csrf_token):
        response = client.get("/fencers")

    assert response.status_code == 200
    assert "Fencer One" in response.text
    assert "Fencer Two" in response.text
    assert "(saber)" in response.text

def test_add_fencer_shows_flash_message(monkeypatch, db_session):
    password_hash = auth_service.hash_password("flash-test")
    user = crud.create_user(db_session, "flash-user", "flash@example.com", password_hash)
    db_session.commit()

    from app.api import tracked_fencers as tracked_fencers_module

    monkeypatch.setattr(
        tracked_fencers_module.fencer_scraper_service,
        "fetch_fencer_display_name",
        lambda *_args, **_kwargs: None,
    )

    with _authenticated_client(db_session, user) as (client, csrf_token):
        response = client.post(
            "/fencers",
            data={"fencer_id": "999", "csrf_token": csrf_token},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "Fencer tracked successfully" in response.text
