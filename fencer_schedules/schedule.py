from __future__ import annotations

import re
import unicodedata
from datetime import date, time

from fencer_schedules.club import is_our_club
from fencer_schedules.config import Settings
from fencer_schedules.models import UNKNOWN_DAY, Event, Fencer, Tournament


def result_place(event: Event, fencer: Fencer) -> str | None:
    """Return a fencer's final place when the event results are cached.

    USA Fencing may append country flags or other display symbols to result
    names. Membership IDs are the strongest identity match; normalized
    name/club matching keeps fixtures and sources without IDs working.
    """
    results = event.results or []
    if fencer.membership_id:
        for result in results:
            if result.membership_id and result.membership_id == fencer.membership_id:
                return result.place

    wanted_name = _person_name(fencer.name)
    wanted_club = _text_key(fencer.club)
    for result in results:
        if _person_name(result.name) == wanted_name and _text_key(result.club) == wanted_club:
            return result.place
    return None


def _person_name(value: str) -> str:
    """Normalize source display decorations such as trailing country flags."""
    value = unicodedata.normalize("NFKC", value).replace("’", "'")
    return " ".join(
        "".join(char if (char.isalnum() or char in " ,.'-") else " " for char in value.casefold()).split()
    )


def _text_key(value: str) -> str:
    return " ".join(value.casefold().split())


def preserve_cached_results(old: Tournament, fresh: Tournament) -> Tournament:
    """Carry fetched final results across a roster refresh by stable event ID."""
    old_results = {
        event.source_event_id: event.results
        for event in old.events
        if event.results is not None
    }
    changed = False
    events: list[Event] = []
    for event in fresh.events:
        results = old_results.get(event.source_event_id)
        if event.results is None and results is not None:
            event = event.model_copy(update={"results": results})
            changed = True
        events.append(event)
    merged = fresh.model_copy(update={"events": events}) if changed else fresh
    if old.results_checked:
        merged = merged.model_copy(update={"results_checked": old.results_checked})
    return merged


def merge_refresh(old: Tournament, fresh: Tournament) -> Tournament:
    """Fold a fresh fetch into the stored copy without losing user state.

    Shared by the manual Refresh button and the background watcher so both
    preserve cached final results and manual/hidden tracking choices.
    """
    return apply_overrides(preserve_cached_results(old, fresh), tracking_overrides(old))


def day_label(value: date) -> str:
    """Human day for an event; never invents a date the source omitted."""
    if value == UNKNOWN_DAY:
        return "Day TBD"
    return value.strftime("%A, %B %-d")


def day_parts(value: date) -> tuple[str, str]:
    """Short (weekday, month day) pair for the jump-to-day tabs."""
    if value == UNKNOWN_DAY:
        return ("TBD", "")
    return (value.strftime("%a"), value.strftime("%b %-d"))


def result_label(event: Event, fencer: Fencer) -> str | None:
    """Return a human-readable final place, including tie wording."""
    place = result_place(event, fencer)
    if place is None:
        return None
    tie_place = _tie_place(event, place)
    if tie_place is not None:
        return f"Tied for {_ordinal(tie_place)}"
    if place.isdigit():
        return _ordinal(int(place))
    return place


def _tie_place(event: Event, place: str) -> int | None:
    """Return the tied rank represented by a source place, if applicable."""
    marker = place.strip()
    tie_marker = re.fullmatch(r"(\d+)\s*[Tt]", marker)
    if tie_marker:
        return int(tie_marker.group(1))
    numeric = re.fullmatch(r"(\d+)(?:\.(\d+))?", marker)
    if not numeric:
        return None
    whole = int(numeric.group(1))
    fraction = numeric.group(2)
    if fraction == "5":
        return whole
    if fraction is not None:
        return None
    if sum(1 for result in (event.results or []) if result.place.strip() == marker) > 1:
        return whole
    return None


def _ordinal(value: int) -> str:
    if 10 < value % 100 < 14:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


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
    # Events whose day was never published sort last rather than pretending to
    # be the earliest thing on the schedule.
    return (event.day_unknown, event.day, event.clock or time.max, event.name)
