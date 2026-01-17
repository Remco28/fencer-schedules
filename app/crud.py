"""CRUD operations for user authentication."""
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


# User CRUD operations


def create_user(
    db: Session,
    username: str,
    email: str,
    password_hash: str,
    is_admin: bool = False,
) -> models.User:
    user = models.User(
        username=username,
        email=email,
        password_hash=password_hash,
        is_admin=is_admin,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.username == username)
        .one_or_none()
    )


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).one_or_none()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.email == email)
        .one_or_none()
    )


def get_active_users(db: Session) -> List[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.is_active.is_(True))
        .all()
    )


def update_user(db: Session, user_id: int, **kwargs) -> models.User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found")

    for field, value in kwargs.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)

    db.flush()
    return user


def update_user_profile(
    db: Session,
    user_id: int,
    username: str,
    email: str,
    club: Optional[str],
) -> models.User:
    """Update user profile fields."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found")

    user.username = username
    user.email = email
    user.club = club

    db.flush()
    return user


def add_tracked_fencer(
    db: Session,
    tournament_id: int,
    fencer_name: str,
    source: str = "manual",
) -> models.TrackedFencer:
    """Add a fencer to tracking list."""
    fencer = models.TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name=fencer_name.strip(),
        source=source,
    )
    db.add(fencer)
    db.flush()
    return fencer


def remove_tracked_fencer(db: Session, fencer_id: int, tournament_id: int) -> bool:
    """Remove a tracked fencer. Returns True if deleted."""
    fencer = (
        db.query(models.TrackedFencer)
        .filter(
            models.TrackedFencer.id == fencer_id,
            models.TrackedFencer.tracked_tournament_id == tournament_id,
        )
        .first()
    )
    if fencer:
        db.delete(fencer)
        db.flush()
        return True
    return False


def get_tracked_fencers(db: Session, tournament_id: int) -> List[models.TrackedFencer]:
    """Get all tracked fencers for a tournament."""
    return (
        db.query(models.TrackedFencer)
        .filter(models.TrackedFencer.tracked_tournament_id == tournament_id)
        .order_by(models.TrackedFencer.fencer_name)
        .all()
    )


def is_fencer_tracked(db: Session, tournament_id: int, fencer_name: str) -> bool:
    """Check if a fencer is already tracked."""
    normalized = fencer_name.strip().lower()
    return (
        db.query(models.TrackedFencer)
        .filter(
            models.TrackedFencer.tracked_tournament_id == tournament_id,
            func.lower(models.TrackedFencer.fencer_name) == normalized,
        )
        .first()
    ) is not None


# Session management


def create_session(
    db: Session,
    user_id: int,
    session_token: str,
    expires_at: datetime,
    csrf_token: Optional[str] = None,
) -> models.UserSession:
    session = models.UserSession(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at,
        csrf_token=csrf_token,
    )
    db.add(session)
    db.flush()
    return session


def get_session(db: Session, session_token: str) -> Optional[models.UserSession]:
    return (
        db.query(models.UserSession)
        .filter(models.UserSession.session_token == session_token)
        .one_or_none()
    )


def delete_session(db: Session, session_token: str) -> None:
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.session_token == session_token)
        .one_or_none()
    )
    if session:
        db.delete(session)
        db.flush()


def cleanup_expired_sessions(db: Session) -> int:
    deleted = (
        db.query(models.UserSession)
        .filter(models.UserSession.expires_at < datetime.now(UTC))
        .delete(synchronize_session=False)
    )
    if deleted:
        db.flush()
    return deleted
