from __future__ import annotations

from datetime import time

from fencer_schedules.club import is_our_club
from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament


def fencer_key(fencer: Fencer) -> tuple[str, str]:
    return (fencer.name.casefold(), fencer.club.casefold())


def is_tracked(fencer: Fencer, settings: Settings) -> bool:
    if fencer.source == "hidden":
        return False
    return fencer.source == "manual" or is_our_club(fencer.club, settings)


def visible_events(tournament: Tournament, settings: Settings) -> list[Event]:
    """Events that have at least one tracked fencer (PDF / club list)."""
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


def other_events(tournament: Tournament, settings: Settings) -> list[Event]:
    """Events with nobody tracked yet — still listed so you can open them."""
    if not tournament.names_available:
        return []
    tracked_ids = {e.source_event_id for e in visible_events(tournament, settings)}
    rest = [e.model_copy(update={"fencers": []}) for e in tournament.events if e.source_event_id not in tracked_ids]
    rest.sort(key=_event_sort)
    return rest


def event_by_id(tournament: Tournament, event_id: str) -> Event | None:
    return next((e for e in tournament.events if e.source_event_id == event_id), None)


def search_loaded_fencers(tournament: Tournament, query: str) -> list[Fencer]:
    needle = query.strip().casefold()
    if not needle:
        return []
    seen: set[tuple[str, str]] = set()
    hits: list[Fencer] = []
    for event in tournament.events:
        for fencer in event.fencers:
            key = fencer_key(fencer)
            if key in seen:
                continue
            if needle in fencer.name.casefold():
                seen.add(key)
                hits.append(fencer)
    return hits


def set_source(
    tournament: Tournament,
    name: str,
    club: str,
    source: str,
) -> Tournament:
    want = (name.casefold(), club.casefold())
    events: list[Event] = []
    for event in tournament.events:
        updated = [
            fencer.model_copy(update={"source": source})
            if fencer_key(fencer) == want
            else fencer
            for fencer in event.fencers
        ]
        events.append(event.model_copy(update={"fencers": updated}))
    return tournament.model_copy(update={"events": events})


def track_named(tournament: Tournament, name: str, club: str, settings: Settings) -> Tournament:
    source = "club" if is_our_club(club, settings) else "manual"
    return set_source(tournament, name, club, source)


def untrack_named(tournament: Tournament, name: str, club: str) -> Tournament:
    return set_source(tournament, name, club, "hidden")


def add_manual(tournament: Tournament, query: str, settings: Settings | None = None) -> Tournament:
    settings = settings or Settings(club_name="", club_aliases=[])
    result = tournament
    for fencer in search_loaded_fencers(tournament, query):
        result = track_named(result, fencer.name, fencer.club, settings)
    return result


def tracking_overrides(tournament: Tournament) -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for event in tournament.events:
        for fencer in event.fencers:
            if fencer.source not in {"manual", "hidden"}:
                continue
            key = (fencer.name, fencer.club)
            if key in seen:
                continue
            seen.add(key)
            out.append((fencer.name, fencer.club, fencer.source))
    return out


def apply_overrides(tournament: Tournament, overrides: list[tuple[str, str, str]]) -> Tournament:
    result = tournament
    for name, club, source in overrides:
        result = set_source(result, name, club, source)
    return result


def _event_sort(event: Event) -> tuple:
    return (event.day, event.clock or time.max, event.name)
