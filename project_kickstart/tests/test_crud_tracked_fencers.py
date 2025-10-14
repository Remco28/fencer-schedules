"""Tests for tracked fencer CRUD operations."""

import pytest
from datetime import UTC, datetime
from sqlalchemy.orm import Session

from app import crud, models


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = crud.create_user(
        db_session,
        username="testuser",
        email="test@example.com",
        password_hash="hashed",
    )
    db_session.commit()
    return user


def test_create_tracked_fencer(db_session: Session, test_user: models.User):
    """Test creating a tracked fencer."""
    tracked_fencer = crud.create_tracked_fencer(
        db_session,
        user_id=test_user.id,
        fencer_id="12345",
        display_name="Test Fencer",
        weapon_filter="foil,epee",
    )
    db_session.commit()

    assert tracked_fencer.id is not None
    assert tracked_fencer.user_id == test_user.id
    assert tracked_fencer.fencer_id == "12345"
    assert tracked_fencer.display_name == "Test Fencer"
    assert tracked_fencer.weapon_filter == "foil,epee"
    assert tracked_fencer.active is True
    assert tracked_fencer.failure_count == 0


def test_get_tracked_fencer_by_id(db_session: Session, test_user: models.User):
    """Test getting a tracked fencer by ID."""
    tracked = crud.create_tracked_fencer(
        db_session,
        user_id=test_user.id,
        fencer_id="12345",
    )
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result is not None
    assert result.id == tracked.id
    assert result.fencer_id == "12345"


def test_get_tracked_fencer_for_user(db_session: Session, test_user: models.User):
    """Test getting a tracked fencer for a specific user."""
    tracked = crud.create_tracked_fencer(
        db_session,
        user_id=test_user.id,
        fencer_id="12345",
    )
    db_session.commit()

    result = crud.get_tracked_fencer_for_user(db_session, test_user.id, "12345")
    assert result is not None
    assert result.fencer_id == "12345"

    # Different fencer_id should return None
    result = crud.get_tracked_fencer_for_user(db_session, test_user.id, "99999")
    assert result is None


def test_get_all_tracked_fencers_for_user(db_session: Session, test_user: models.User):
    """Test getting all tracked fencers for a user."""
    # Create multiple tracked fencers
    crud.create_tracked_fencer(db_session, test_user.id, "111", "Fencer 1")
    crud.create_tracked_fencer(db_session, test_user.id, "222", "Fencer 2")
    crud.create_tracked_fencer(db_session, test_user.id, "333", "Fencer 3", weapon_filter="epee")
    db_session.commit()

    # Get all active
    result = crud.get_all_tracked_fencers_for_user(db_session, test_user.id, active_only=True)
    assert len(result) == 3

    # Deactivate one and test active_only filter
    fencer = crud.get_tracked_fencer_for_user(db_session, test_user.id, "222")
    crud.deactivate_tracked_fencer(db_session, fencer)
    db_session.commit()

    result = crud.get_all_tracked_fencers_for_user(db_session, test_user.id, active_only=True)
    assert len(result) == 2

    result = crud.get_all_tracked_fencers_for_user(db_session, test_user.id, active_only=False)
    assert len(result) == 3


def test_get_all_active_tracked_fencers(db_session: Session, test_user: models.User):
    """Test getting all active tracked fencers across all users."""
    # Create another user
    user2 = crud.create_user(db_session, "user2", "user2@example.com", "hashed")
    db_session.commit()

    # Create tracked fencers for both users
    crud.create_tracked_fencer(db_session, test_user.id, "111")
    crud.create_tracked_fencer(db_session, test_user.id, "222")
    crud.create_tracked_fencer(db_session, user2.id, "333")
    db_session.commit()

    result = crud.get_all_active_tracked_fencers(db_session)
    assert len(result) == 3


def test_update_tracked_fencer(db_session: Session, test_user: models.User):
    """Test updating a tracked fencer."""
    tracked = crud.create_tracked_fencer(
        db_session,
        test_user.id,
        "12345",
        "Original Name",
        "foil",
    )
    db_session.commit()

    crud.update_tracked_fencer(
        db_session,
        tracked,
        display_name="Updated Name",
        weapon_filter="epee,saber",
    )
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result.display_name == "Updated Name"
    assert result.weapon_filter == "epee,saber"


def test_deactivate_tracked_fencer(db_session: Session, test_user: models.User):
    """Test deactivating a tracked fencer."""
    tracked = crud.create_tracked_fencer(db_session, test_user.id, "12345")
    db_session.commit()

    assert tracked.active is True

    crud.deactivate_tracked_fencer(db_session, tracked)
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result.active is False


def test_update_fencer_check_status_success(db_session: Session, test_user: models.User):
    """Test updating fencer check status on success."""
    tracked = crud.create_tracked_fencer(db_session, test_user.id, "12345")
    # Simulate previous failures
    tracked.failure_count = 2
    tracked.last_failure_at = datetime.now(UTC)
    db_session.commit()

    check_time = datetime.now(UTC)
    crud.update_fencer_check_status(db_session, tracked, check_time, success=True)
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result.last_checked_at == check_time
    assert result.failure_count == 0
    assert result.last_failure_at is None


def test_update_fencer_check_status_failure(db_session: Session, test_user: models.User):
    """Test updating fencer check status on failure."""
    tracked = crud.create_tracked_fencer(db_session, test_user.id, "12345")
    db_session.commit()

    check_time = datetime.now(UTC)
    crud.update_fencer_check_status(db_session, tracked, check_time, success=False)
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result.last_checked_at == check_time
    assert result.failure_count == 1
    assert result.last_failure_at == check_time


def test_get_registrations_for_fencer(db_session: Session, test_user: models.User):
    """Test getting registrations for a fencer by fencingtracker_id."""
    # Create a fencer with fencingtracker_id
    fencer = crud.get_or_create_fencer(db_session, "Test Fencer")
    fencer.fencingtracker_id = "12345"

    # Create tournaments and registrations
    tournament1 = crud.get_or_create_tournament(db_session, "Tournament 1", "2024-01-01")
    tournament2 = crud.get_or_create_tournament(db_session, "Tournament 2", "2024-01-15")

    crud.update_or_create_registration(db_session, fencer, tournament1, "Foil", "http://test.com")
    crud.update_or_create_registration(db_session, fencer, tournament2, "Epee", "http://test.com")
    db_session.commit()

    # Query by fencingtracker_id
    result = crud.get_registrations_for_fencer(db_session, "12345")
    assert len(result) == 2

    # Non-existent fencingtracker_id should return empty list
    result = crud.get_registrations_for_fencer(db_session, "99999")
    assert len(result) == 0

from sqlalchemy.exc import IntegrityError

def test_create_duplicate_tracked_fencer_raises_error(db_session: Session, test_user: models.User):
    """Test that creating a duplicate tracked fencer for the same user raises an IntegrityError."""
    crud.create_tracked_fencer(db_session, test_user.id, "12345")
    db_session.commit()

    with pytest.raises(IntegrityError):
        crud.create_tracked_fencer(db_session, test_user.id, "12345")
        db_session.commit()

def test_deactivate_tracked_fencer_updates_fields(db_session: Session, test_user: models.User):
    """Test that deactivating a fencer sets active=False and updates the timestamp."""
    tracked = crud.create_tracked_fencer(db_session, test_user.id, "12345")
    db_session.commit()

    assert tracked.active is True
    assert tracked.updated_at is not None
    original_updated_at = tracked.updated_at

    crud.deactivate_tracked_fencer(db_session, tracked)
    db_session.commit()

    result = crud.get_tracked_fencer_by_id(db_session, tracked.id)
    assert result.active is False
    assert result.updated_at > original_updated_at

