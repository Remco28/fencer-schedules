"""User authentication models."""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from datetime import UTC, datetime

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    club = Column(String(200), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tracked_tournaments = relationship(
        "TrackedTournament",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String, unique=True, nullable=False, index=True)
    csrf_token = Column(String(128), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    user = relationship("User", back_populates="sessions")


class TrackedTournament(Base):
    __tablename__ = "tracked_tournaments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tournament_id = Column(String(32), nullable=False)
    tournament_name = Column(String(300), nullable=False)
    tournament_url = Column(String(500), nullable=False)
    club_filter = Column(String(200), nullable=True)
    weapon_filter = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    user = relationship("User", back_populates="tracked_tournaments")
    events = relationship(
        "CachedEvent",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    tracked_fencers = relationship(
        "TrackedFencer",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )


class CachedEvent(Base):
    __tablename__ = "cached_events"

    id = Column(Integer, primary_key=True, index=True)
    tracked_tournament_id = Column(Integer, ForeignKey("tracked_tournaments.id"), nullable=False, index=True)
    event_id = Column(String(32), nullable=False)
    event_name = Column(String(300), nullable=False)
    weapon = Column(String(20), nullable=True)
    start_date = Column(String(50), nullable=True)
    start_time = Column(String(20), nullable=True)
    pool_round_id = Column(String(32), nullable=True)
    de_round_id = Column(String(32), nullable=True)
    fencer_count = Column(Integer, default=0)

    tournament = relationship("TrackedTournament", back_populates="events")


class TrackedFencer(Base):
    __tablename__ = "tracked_fencers"

    id = Column(Integer, primary_key=True, index=True)
    tracked_tournament_id = Column(
        Integer, ForeignKey("tracked_tournaments.id"), nullable=False, index=True
    )
    fencer_name = Column(String(200), nullable=False)
    source = Column(String(20), nullable=False, default="manual")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    tournament = relationship("TrackedTournament", back_populates="tracked_fencers")
