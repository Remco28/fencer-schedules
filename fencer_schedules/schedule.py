from __future__ import annotations

from datetime import time

from fencer_schedules.club import is_our_club
from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament


def is_tracked(fencer: Fencer, settings: Settings) -> bool:
    return fencer.source == "manual" or is_our_club(fencer.club, settings)


def visible_events(tournament: Tournament, settings: Settings) -> list[Event]:
    if not tournament.names_available:
        return sorted(tournament.events, key=_event_sort)
    kept: list[Event] = []
    for event in tournament.events:
        tracked = [f for f in event.fencers if is_tracked(f, settings)]
        if not tracked:
            continue
        kept.append(event.model_copy(update={"fencers": tracked}))
    kept.sort(key=_event_sort)
    return kept


def search_loaded_fencers(tournament: Tournament, query: str) -> list[Fencer]:
    needle = query.strip().casefold()
    if not needle:
        return []
    seen: set[tuple[str, str]] = set()
    hits: list[Fencer] = []
    for event in tournament.events:
        for fencer in event.fencers:
            key = (fencer.name.casefold(), fencer.club.casefold())
            if key in seen:
                continue
            if needle in fencer.name.casefold():
                seen.add(key)
                hits.append(fencer)
    return hits


def add_manual(tournament: Tournament, query: str) -> Tournament:
    matches = search_loaded_fencers(tournament, query)
    if not matches:
        return tournament
    wanted = {(f.name.casefold(), f.club.casefold()) for f in matches}
    events: list[Event] = []
    for event in tournament.events:
        updated = [
            fencer.model_copy(update={"source": "manual"})
            if (fencer.name.casefold(), fencer.club.casefold()) in wanted
            else fencer
            for fencer in event.fencers
        ]
        events.append(event.model_copy(update={"fencers": updated}))
    return tournament.model_copy(update={"events": events})


def _event_sort(event: Event) -> tuple:
    return (event.day, event.clock or time.max, event.name)
