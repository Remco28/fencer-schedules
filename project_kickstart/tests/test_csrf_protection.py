import pytest
from contextlib import contextmanager

try:  # pragma: no cover - optional dependency for TestClient
    import httpx  # type: ignore
    HAS_HTTPX = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_HTTPX = False

if HAS_HTTPX:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")

from app import crud
from app.api.dependencies import SESSION_COOKIE_NAME
from app.database import get_db
from app.main import app
from app.services import auth_service, csrf_service


def _create_user(db_session, username: str = "csfr-user"):
    password_hash = auth_service.hash_password("example-password")
    user = crud.create_user(db_session, username, f"{username}@example.com", password_hash)
    db_session.commit()
    return user


@contextmanager
def _authenticated_client(db_session, user=None):
    if user is None:
        user = _create_user(db_session)

    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    session = crud.get_session(db_session, token)
    csrf_token = session.csrf_token if session else ""

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override

    try:
        with TestClient(app) as client:
            client.cookies.set(SESSION_COOKIE_NAME, token)
            yield client, user, csrf_token
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_csrf_token_generated_on_session_creation(db_session):
    user = _create_user(db_session, "session-user")
    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    session = crud.get_session(db_session, token)
    assert session is not None
    assert session.csrf_token
    assert len(session.csrf_token) == 64


def test_csrf_token_validation_success(db_session):
    user = _create_user(db_session, "validate-user")
    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    session = crud.get_session(db_session, token)
    assert session is not None
    assert csrf_service.validate_csrf_token(token, session.csrf_token, db_session)


def test_csrf_token_validation_failure_missing(db_session):
    user = _create_user(db_session, "missing-user")
    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    assert csrf_service.validate_csrf_token(token, None, db_session) is False
    assert csrf_service.validate_csrf_token(None, "", db_session) is False


def test_csrf_token_validation_failure_invalid(db_session):
    user = _create_user(db_session, "invalid-user")
    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    assert csrf_service.validate_csrf_token(token, "deadbeef", db_session) is False


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_csrf_token_in_template_context(db_session):
    user = _create_user(db_session, "template-user")

    with _authenticated_client(db_session, user) as (client, _user, csrf_token):
        response = client.get("/clubs")

    assert response.status_code == 200
    assert csrf_token in response.text
    assert '<input type="hidden" name="csrf_token"' in response.text


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_logout_requires_csrf_token(db_session):
    user = _create_user(db_session, "logout-user")

    with _authenticated_client(db_session, user) as (client, _user, csrf_token):
        without_token = client.post("/auth/logout")
        assert without_token.status_code == 403

        with_token = client.post("/auth/logout", data={"csrf_token": csrf_token})

    assert with_token.status_code == 303


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_club_add_requires_csrf_token(monkeypatch, db_session):
    user = _create_user(db_session, "club-user")

    from app.api import clubs as clubs_module

    monkeypatch.setattr(
        clubs_module,
        "validate_club_url",
        lambda club_url, timeout=10: (club_url, "Club Name"),
    )

    with _authenticated_client(db_session, user) as (client, _user, csrf_token):
        payload = {
            "club_url": "https://fencingtracker.com/club/example/registrations",
            "club_name": "Example Club",
        }
        forbidden = client.post("/clubs/add", data=payload)
        assert forbidden.status_code == 403

        payload["csrf_token"] = csrf_token
        allowed = client.post("/clubs/add", data=payload)

    assert allowed.status_code == 303


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not available for TestClient")
def test_fencer_add_requires_csrf_token(db_session):
    user = _create_user(db_session, "fencer-user")

    with _authenticated_client(db_session, user) as (client, _user, csrf_token):
        payload = {
            "fencer_id": "https://fencingtracker.com/p/44444/test-fencer",
            "weapon_filter": "foil,epee",
        }
        forbidden = client.post("/fencers", data=payload)
        assert forbidden.status_code == 403

        payload["csrf_token"] = csrf_token
        allowed = client.post("/fencers", data=payload)

    assert allowed.status_code == 303
