"""Lightweight database setup for FTL live tracking."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLite database URL (local dev default)
SQLALCHEMY_DATABASE_URL = "sqlite:///./fencer_schedules.db"

Base = declarative_base()

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create tables for all registered models."""
    # Import models to register them with Base metadata
    import app.ftl.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI-style dependency for DB session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
