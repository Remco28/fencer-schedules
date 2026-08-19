from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field


class Fencer(BaseModel):
    name: str
    club: str
    source: Literal["club", "manual", "hidden"] = "club"
    membership_id: str | None = None


class Event(BaseModel):
    source_event_id: str
    name: str
    day: date
    clock: time | None = None
    clock_label: str | None = None
    fencers: list[Fencer] = Field(default_factory=list)


class Tournament(BaseModel):
    askfred_id: str
    name: str
    start_date: date
    end_date: date
    usfa_id: str | None = None
    venue: str | None = None
    events: list[Event] = Field(default_factory=list)
    names_available: bool = True
