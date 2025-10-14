from datetime import UTC, datetime, timedelta

import pytest

from app import crud
from app.services import auth_service


def test_hash_and_verify_password():
    password = "swordfish123"
    hashed = auth_service.hash_password(password)

    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("wrong", hashed)


def test_register_user_creates_account(db_session):
    user = auth_service.register_user("alice", "alice@example.com", "password123", db_session)
    db_session.commit()

    assert user.username == "alice"
    assert user.email == "alice@example.com"


def test_register_user_rejects_duplicate_username(db_session):
    auth_service.register_user("bob", "bob@example.com", "password123", db_session)
    db_session.commit()

    with pytest.raises(ValueError):
        auth_service.register_user("bob", "other@example.com", "password123", db_session)


def test_authenticate_returns_user_on_valid_credentials(db_session):
    auth_service.register_user("carol", "carol@example.com", "password123", db_session)
    db_session.commit()

    user = auth_service.authenticate("carol", "password123", db_session)

    assert user is not None
    assert user.username == "carol"


def test_authenticate_returns_none_for_invalid_password(db_session):
    auth_service.register_user("dan", "dan@example.com", "password123", db_session)
    db_session.commit()

    assert auth_service.authenticate("dan", "wrong", db_session) is None


def test_session_lifecycle(db_session):
    user = auth_service.register_user("eve", "eve@example.com", "password123", db_session)
    db_session.commit()

    token, _ = auth_service.create_session(db_session, user.id)
    db_session.commit()

    assert auth_service.validate_session(db_session, token).id == user.id

    auth_service.logout(db_session, token)
    db_session.commit()

    assert auth_service.validate_session(db_session, token) is None


def test_validate_session_expires_old_tokens(db_session):
    user = auth_service.register_user("frank", "frank@example.com", "password123", db_session)
    db_session.commit()

    expired_time = datetime.now(UTC) - timedelta(days=1)
    crud.create_session(db_session, user.id, "expired", expired_time)
    db_session.commit()

    assert auth_service.validate_session(db_session, "expired") is None
