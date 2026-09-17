from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

# Sentinel for "the source never published a day". Sorts last and is rendered
# as "Day TBD" instead of a fabricated date.
UNKNOWN_DAY = date.max


class Fencer(BaseModel):
    name: str
    club: str
    source: Literal["club", "manual", "hidden"] = "club"
    membership_id: str | None = None


class EventResult(BaseModel):
    place: str
    name: str
    club: str
    membership_id: str | None = None


class Event(BaseModel):
    source_event_id: str
    name: str
    day: date
    clock: time | None = None
    clock_label: str | None = None
    # True when the source never published a day for this event; the stored
    # `day` is then only a sort key and must not be shown as a real date.
    day_unknown: bool = False
    fencers: list[Fencer] = Field(default_factory=list)
    results: list[EventResult] | None = None


class Tournament(BaseModel):
    askfred_id: str
    name: str
    start_date: date
    end_date: date
    usfa_id: str | None = None
    venue: str | None = None
    events: list[Event] = Field(default_factory=list)
    names_available: bool = True
    # event id -> when results were last sought, so an event whose results are
    # not published yet is not re-fetched on every page load.
    results_checked: dict[str, datetime] = Field(default_factory=dict)
