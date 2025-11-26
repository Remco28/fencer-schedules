"""Pydantic schemas for FTL API responses."""
from typing import Optional
from pydantic import BaseModel


class PoolIdListing(BaseModel):
    """Response schema for pool ID extraction."""
    event_id: Optional[str] = None
    pool_round_id: str
    pool_ids: list[str]


class PoolBout(BaseModel):
    """Individual bout within a pool."""
    fencer_a: str
    fencer_b: str
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    winner: Optional[str] = None  # "A" | "B" | None
    status: str  # "complete" | "incomplete"


class PoolFencer(BaseModel):
    """Fencer participating in a pool."""
    name: str
    club: Optional[str] = None
    seed: Optional[int] = None
    indicator: Optional[str] = None  # e.g., "+14", "-5"


class PoolDetails(BaseModel):
    """Complete pool data including strip, fencers, and bouts."""
    pool_id: Optional[str] = None
    pool_number: int
    strip: Optional[str] = None
    fencers: list[PoolFencer]
    bouts: list[PoolBout]


class PoolResult(BaseModel):
    """Individual fencer result from pool rounds with advancement status."""
    fencer_id: str
    name: str
    club_primary: Optional[str] = None
    club_secondary: Optional[str] = None
    division: Optional[str] = None
    country: Optional[str] = None
    place: Optional[int] = None
    victories: int
    matches: int
    victory_ratio: Optional[float] = None
    touches_scored: Optional[int] = None
    touches_received: Optional[int] = None
    indicator: Optional[int] = None
    prediction_raw: Optional[str] = None
    status: str  # "advanced" | "eliminated" | "unknown"
    tie: Optional[bool] = None


class PoolResults(BaseModel):
    """Complete pool results for an event/round with all fencer outcomes."""
    event_id: Optional[str] = None
    pool_round_id: Optional[str] = None
    fencers: list[PoolResult]
