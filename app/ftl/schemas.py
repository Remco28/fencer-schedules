"""Pydantic schemas for FTL API responses."""
from typing import Optional
from pydantic import BaseModel


class PoolIdListing(BaseModel):
    """Response schema for pool ID extraction."""
    event_id: Optional[str] = None
    pool_round_id: str
    pool_ids: list[str]
