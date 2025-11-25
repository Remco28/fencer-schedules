"""FTL database models for event linkage and caching."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, Index

from app.database import Base


class FTLEventLink(Base):
    """Links user-provided FTL URLs to event and round IDs."""
    __tablename__ = "ftl_event_links"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(32), nullable=False, unique=True, index=True)
    pool_round_id = Column(String(32), nullable=False)
    de_round_id = Column(String(32), nullable=True)
    source_url = Column(String, nullable=False)
    label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FTLPoolsSnapshot(Base):
    """Cache of pool ID listings to reduce repeated fetches."""
    __tablename__ = "ftl_pools_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(32), nullable=False, index=True)
    pool_round_id = Column(String(32), nullable=False, index=True)
    pool_ids = Column(Text, nullable=False)  # JSON serialized list of pool IDs
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_ftl_pools_event_round', 'event_id', 'pool_round_id'),
    )
