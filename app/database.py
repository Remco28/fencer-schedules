"""Lightweight database setup for FTL live tracking."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database URL from environment or local SQLite default
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fencer_schedules.db")

# Heroku/Railway often provide 'postgres://', but SQLAlchemy requires 'postgresql://'
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()

# Create engine
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Postgres configuration
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create tables for all registered models."""
    # Import models to register them with Base metadata
    import app.ftl.models  # noqa: F401
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI-style dependency for DB session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
