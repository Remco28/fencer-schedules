from __future__ import annotations

import logging
from datetime import datetime, time

from fencer_schedules.config import Settings
from fencer_schedules.fencing_api import FencingApi, NotAvailable, StillLoading
from fencer_schedules.models import Event, Fencer, Tournament

logger = logging.getLogger("fencer_schedules.load")


def load_tournament(
    askfred_id: str,
    settings: Settings,
    api: FencingApi | None = None,
    wait_s: float | None = None,
) -> Tournament:
    """One tournament with every event and its entrants, all from fencing-api.

    Regional/national tournaments (AskFRED links to USA Fencing) take events and
    names from USA Fencing; locals take AskFRED events plus preregistration names.
    Raises StillLoading when fencing-api is still reading a big tournament.
    """
    api = api or settings.fencing_api()
    first_read = len(api.reads)
    tournament = _load(askfred_id, api, wait_s)
    reads = api.reads[first_read:]
    if reads:
        tournament.data_as_of = min(datetime.fromisoformat(at.replace("Z", "+00:00")) for at, _ in reads)
        tournament.data_stale = any(stale for _, stale in reads)
    return tournament


def _load(askfred_id: str, api: FencingApi, wait_s: float | None) -> Tournament:
    tournament, askfred_events = api.tournament(askfred_id, wait_s=wait_s)
    if not tournament.usfa_id:
        tournament.events = _with_askfred_names(askfred_events, askfred_id, api, wait_s)
        tournament.names_available = any(event.fencers for event in tournament.events)
        return tournament

    usfa_events = api.usfa_tournament_entries(tournament.usfa_id, wait_s=wait_s)
    clocks = _clocks_by_name(askfred_events)
    filled: list[Event] = []
    for event in usfa_events:
        clock, label = event.clock, event.clock_label
        if clock is None:
            clock, label = clocks.get(_norm(event.name), (None, None))
        filled.append(event.model_copy(update={"clock": clock, "clock_label": label}))
    tournament.events = filled
    tournament.names_available = True
    return tournament


def _with_askfred_names(events: list[Event], askfred_id: str, api: FencingApi, wait_s: float | None) -> list[Event]:
    try:
        registrations = api.askfred_entries(askfred_id, wait_s=wait_s)
    except StillLoading:
        raise
    except NotAvailable:
        return events
    except Exception:
        logger.warning("AskFRED registrations failed for %s", askfred_id, exc_info=True)
        return events
    index: dict[str, list[Fencer]] = {_norm(title): fencers for title, _, fencers in registrations}
    clocks: dict[str, time] = {_norm(title): clock for title, clock, _ in registrations if clock}
    attached: list[Event] = []
    for event in events:
        fencers = _match_event_fencers(event.name, index)
        clock = event.clock or clocks.get(_norm(event.name))
        if clock is None:
            for title, value in clocks.items():
                if _norm(event.name) in title or title in _norm(event.name):
                    clock = value
                    break
        attached.append(event.model_copy(update={"fencers": fencers, "clock": clock}))
    return attached


def _match_event_fencers(name: str, index: dict[str, list[Fencer]]) -> list[Fencer]:
    key = _norm(name)
    if key in index:
        return index[key]
    for title, fencers in index.items():
        if key in title or title in key:
            return fencers
    return []


def _norm(name: str) -> str:
    return " ".join(name.replace("’", "'").casefold().split())


def _clocks_by_name(events: list[Event]) -> dict[str, tuple]:
    return {_norm(event.name): (event.clock, event.clock_label) for event in events}
