from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    date = Column(String, nullable=False)

    registrations = relationship("Registration", back_populates="tournament")


class Fencer(Base):
    __tablename__ = "fencers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    fencingtracker_id = Column(String, nullable=True, index=True)  # Optional external ID for tracked fencers

    registrations = relationship("Registration", back_populates="fencer")


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    fencer_id = Column(Integer, ForeignKey("fencers.id"), nullable=False)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    events = Column(String, nullable=False)
    club_url = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fencer = relationship("Fencer", back_populates="registrations")
    tournament = relationship("Tournament", back_populates="registrations")

    __table_args__ = (
        UniqueConstraint('fencer_id', 'tournament_id', name='unique_fencer_tournament'),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tracked_clubs = relationship(
        "TrackedClub",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tracked_fencers = relationship(
        "TrackedFencer",
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


class TrackedClub(Base):
    __tablename__ = "tracked_clubs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    club_url = Column(String, nullable=False)
    club_name = Column(String, nullable=True)
    weapon_filter = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="tracked_clubs")

    __table_args__ = (
        UniqueConstraint("user_id", "club_url", name="uq_tracked_clubs_user_club"),
    )


class TrackedFencer(Base):
    __tablename__ = "tracked_fencers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fencer_id = Column(String, nullable=False, index=True)  # fencingtracker numeric ID
    display_name = Column(String, nullable=True)
    weapon_filter = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0, nullable=False)
    last_failure_at = Column(DateTime, nullable=True)
    last_registration_hash = Column(String, nullable=True)  # Cache hash to detect changes

    user = relationship("User", back_populates="tracked_fencers")

    __table_args__ = (
        UniqueConstraint("user_id", "fencer_id", name="uq_tracked_fencers_user_fencer"),
    )
