from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import models


def get_fencer_by_fencingtracker_id(db: Session, fencingtracker_id: str) -> Optional[models.Fencer]:
    """Get a fencer by their fencingtracker ID."""
    return (
        db.query(models.Fencer)
        .filter(models.Fencer.fencingtracker_id == fencingtracker_id)
        .first()
    )


def get_or_create_fencer(db: Session, name: str) -> models.Fencer:
    """Get an existing fencer by name or create a new one if not found."""
    fencer = db.query(models.Fencer).filter(models.Fencer.name == name).first()
    if fencer:
        return fencer

    # Fencer not found, create a new one
    fencer = models.Fencer(name=name)
    db.add(fencer)
    db.flush()  # Flush to get the ID without committing
    return fencer


def get_or_create_tournament(db: Session, name: str, date: str) -> models.Tournament:
    """Get an existing tournament by name or create a new one if not found."""
    tournament = db.query(models.Tournament).filter(models.Tournament.name == name).first()
    if tournament:
        return tournament

    # Tournament not found, create a new one
    tournament = models.Tournament(name=name, date=date)
    db.add(tournament)
    db.flush()  # Flush to get the ID without committing
    return tournament


def update_or_create_registration(
    db: Session,
    fencer: models.Fencer,
    tournament: models.Tournament,
    events: str,
    club_url: str,
) -> tuple[models.Registration, bool]:
    """
    Update an existing registration or create a new one.

    Note: With the corrected scraper, a fencer can have multiple registrations
    for the same tournament (one per event). The unique constraint on
    (fencer_id, tournament_id) means we need to handle this by updating
    the events field to include all events for that tournament.

    Returns:
        tuple[Registration, bool]: The registration object and a boolean indicating
        if it was newly created (True if new, False if it already existed).
    """
    registration = db.query(models.Registration).filter(
        models.Registration.fencer_id == fencer.id,
        models.Registration.tournament_id == tournament.id,
    ).first()

    if registration:
        # Update existing registration
        # If events field doesn't already contain this event, append it
        existing_events = registration.events
        if existing_events and events and events not in existing_events:
            # Append the new event to existing events (comma-separated)
            registration.events = f"{existing_events}, {events}"
        elif not existing_events:
            # No existing events, set it
            registration.events = events
        # Otherwise, event already in the list, just update timestamp

        if not registration.club_url:
            registration.club_url = club_url
        registration.last_seen_at = datetime.now(UTC)
        db.flush()
        return registration, False
    else:
        # Create new registration
        registration = models.Registration(
            fencer_id=fencer.id,
            tournament_id=tournament.id,
            events=events,
            club_url=club_url,
            last_seen_at=datetime.now(UTC)
        )
        db.add(registration)
        try:
            db.flush()
        except IntegrityError:
            # Race condition: registration was created between our query and insert
            # Rollback and retry the query
            db.rollback()
            registration = db.query(models.Registration).filter(
                models.Registration.fencer_id == fencer.id,
                models.Registration.tournament_id == tournament.id,
            ).first()
            if registration:
                # Update the existing registration instead
                existing_events = registration.events
                if existing_events and events and events not in existing_events:
                    registration.events = f"{existing_events}, {events}"
                elif not existing_events:
                    registration.events = events
                if not registration.club_url:
                    registration.club_url = club_url
                registration.last_seen_at = datetime.now(UTC)
                db.flush()
                return registration, False
            else:
                # Still doesn't exist? Re-raise the error
                raise
        return registration, True


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


# Tracked club operations


def create_tracked_club(
    db: Session,
    user_id: int,
    club_url: str,
    club_name: Optional[str] = None,
    weapon_filter: Optional[str] = None,
) -> models.TrackedClub:
    tracked = models.TrackedClub(
        user_id=user_id,
        club_url=club_url,
        club_name=club_name,
        weapon_filter=weapon_filter,
    )
    db.add(tracked)
    db.flush()
    return tracked


def get_tracked_club_by_id(
    db: Session,
    tracked_club_id: int,
) -> Optional[models.TrackedClub]:
    return (
        db.query(models.TrackedClub)
        .filter(models.TrackedClub.id == tracked_club_id)
        .one_or_none()
    )


def get_tracked_club_for_user(
    db: Session,
    tracked_club_id: int,
    user_id: int,
) -> Optional[models.TrackedClub]:
    return (
        db.query(models.TrackedClub)
        .filter(
            models.TrackedClub.id == tracked_club_id,
            models.TrackedClub.user_id == user_id,
        )
        .one_or_none()
    )


def get_tracked_club_by_user_and_url(
    db: Session,
    user_id: int,
    club_url: str,
) -> Optional[models.TrackedClub]:
    return (
        db.query(models.TrackedClub)
        .filter(
            models.TrackedClub.user_id == user_id,
            models.TrackedClub.club_url == club_url,
        )
        .one_or_none()
    )


def get_tracked_clubs(
    db: Session,
    user_id: int,
    active: Optional[bool] = None,
) -> List[models.TrackedClub]:
    query = db.query(models.TrackedClub).filter(models.TrackedClub.user_id == user_id)
    if active is not None:
        query = query.filter(models.TrackedClub.active.is_(active))
    return query.order_by(models.TrackedClub.created_at.desc()).all()


def update_tracked_club(
    db: Session,
    tracked_club_id: int,
    **kwargs,
) -> models.TrackedClub:
    tracked = get_tracked_club_by_id(db, tracked_club_id)
    if not tracked:
        raise ValueError("Tracked club not found")

    for field, value in kwargs.items():
        if hasattr(tracked, field) and value is not None:
            setattr(tracked, field, value)

    db.flush()
    return tracked


def deactivate_tracked_club(db: Session, tracked_club_id: int) -> None:
    tracked = get_tracked_club_by_id(db, tracked_club_id)
    if tracked and tracked.active:
        tracked.active = False
        db.flush()


# Registration queries for digests


def get_registrations_by_club_url(
    db: Session,
    club_url: str,
    since: Optional[datetime] = None,
) -> List[models.Registration]:
    query = (
        db.query(models.Registration)
        .options(
            joinedload(models.Registration.fencer),
            joinedload(models.Registration.tournament),
        )
        .filter(models.Registration.club_url == club_url)
    )
    if since is not None:
        query = query.filter(models.Registration.created_at >= since)
    return query.all()


def get_registration_counts_for_users(db: Session) -> List[dict]:
    rows = (
        db.query(
            models.User.id.label("user_id"),
            func.count(models.TrackedClub.id).label("tracked_club_count"),
        )
        .outerjoin(models.TrackedClub, models.User.id == models.TrackedClub.user_id)
        .group_by(models.User.id)
        .all()
    )
    return [dict(row._mapping) for row in rows]


# Tracked fencer operations


def create_tracked_fencer(
    db: Session,
    user_id: int,
    fencer_id: str,
    display_name: Optional[str] = None,
    weapon_filter: Optional[str] = None,
) -> models.TrackedFencer:
    tracked = models.TrackedFencer(
        user_id=user_id,
        fencer_id=fencer_id,
        display_name=display_name,
        weapon_filter=weapon_filter,
    )
    db.add(tracked)
    db.flush()
    return tracked


def get_tracked_fencer_by_id(
    db: Session,
    tracked_fencer_id: int,
) -> Optional[models.TrackedFencer]:
    return (
        db.query(models.TrackedFencer)
        .filter(models.TrackedFencer.id == tracked_fencer_id)
        .one_or_none()
    )


def get_tracked_fencer_for_user(
    db: Session,
    user_id: int,
    fencer_id: str,
) -> Optional[models.TrackedFencer]:
    return (
        db.query(models.TrackedFencer)
        .filter(
            models.TrackedFencer.user_id == user_id,
            models.TrackedFencer.fencer_id == fencer_id,
        )
        .one_or_none()
    )


def get_all_tracked_fencers_for_user(
    db: Session,
    user_id: int,
    active_only: bool = True,
) -> List[models.TrackedFencer]:
    query = db.query(models.TrackedFencer).filter(
        models.TrackedFencer.user_id == user_id
    )
    if active_only:
        query = query.filter(models.TrackedFencer.active == True)
    return query.order_by(models.TrackedFencer.created_at.desc()).all()


def get_all_active_tracked_fencers(db: Session) -> List[models.TrackedFencer]:
    """Get all active tracked fencers across all users (for scraper)."""
    return (
        db.query(models.TrackedFencer)
        .filter(models.TrackedFencer.active == True)
        .order_by(models.TrackedFencer.user_id, models.TrackedFencer.fencer_id)
        .all()
    )


def update_tracked_fencer(
    db: Session,
    tracked_fencer: models.TrackedFencer,
    display_name: Optional[str] = None,
    weapon_filter: Optional[str] = None,
) -> models.TrackedFencer:
    if display_name is not None:
        tracked_fencer.display_name = display_name
    if weapon_filter is not None:
        tracked_fencer.weapon_filter = weapon_filter
    db.flush()
    return tracked_fencer


def deactivate_tracked_fencer(
    db: Session,
    tracked_fencer: models.TrackedFencer,
) -> models.TrackedFencer:
    tracked_fencer.active = False
    db.flush()
    return tracked_fencer


def update_fencer_check_status(
    db: Session,
    tracked_fencer: models.TrackedFencer,
    last_checked_at: datetime,
    success: bool = True,
) -> models.TrackedFencer:
    """Update last_checked_at and failure tracking for a fencer."""
    tracked_fencer.last_checked_at = last_checked_at
    if success:
        tracked_fencer.failure_count = 0
        tracked_fencer.last_failure_at = None
    else:
        tracked_fencer.failure_count += 1
        tracked_fencer.last_failure_at = last_checked_at
    db.flush()
    return tracked_fencer


def get_registrations_for_fencer(
    db: Session,
    fencingtracker_id: str,
    since: Optional[datetime] = None,
) -> List[models.Registration]:
    """Get registrations for a specific fencer by fencingtracker ID."""
    query = (
        db.query(models.Registration)
        .options(
            joinedload(models.Registration.fencer),
            joinedload(models.Registration.tournament),
        )
        .join(models.Fencer)
        .filter(models.Fencer.fencingtracker_id == fencingtracker_id)
    )
    if since is not None:
        query = query.filter(models.Registration.created_at >= since)
    return query.all()
