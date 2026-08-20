from __future__ import annotations

from typing import Protocol

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament
from fencer_schedules.sources.askfred import AskFredClient
from fencer_schedules.sources.askfred_prereg import AskFredSite
from fencer_schedules.sources.usfa import UsfaClient


class PreregSource(Protocol):
    def fetch_preregistrations(self, tournament_id: str) -> dict[str, list[Fencer]]: ...



def load_tournament(
    askfred_id: str,
    settings: Settings,
    askfred: AskFredClient | None = None,
    usfa: UsfaClient | None = None,
    askfred_site: PreregSource | None = None,
) -> Tournament:
    askfred = askfred or AskFredClient(settings.askfred_api_token)
    tournament = askfred.fetch_tournament(askfred_id)
    askfred_events = askfred.fetch_events(askfred_id)
    if not tournament.usfa_id:
        tournament.events = _with_askfred_names(askfred_events, askfred_id, settings, askfred_site)
        tournament.names_available = any(event.fencers for event in tournament.events)
        return tournament

    usfa = usfa or UsfaClient()
    usfa_events = usfa.fetch_events(tournament.usfa_id, year=tournament.start_date.year)
    clocks = _clocks_by_name(askfred_events)
    filled: list[Event] = []
    for event in usfa_events:
        entrants = usfa.fetch_entrants(tournament.usfa_id, event.source_event_id)
        clock, label = event.clock, event.clock_label
        if clock is None:
            clock, label = clocks.get(_norm(event.name), (None, None))
        filled.append(
            event.model_copy(
                update={"fencers": entrants, "clock": clock, "clock_label": label}
            )
        )
    tournament.events = filled
    tournament.names_available = True
    return tournament


def _with_askfred_names(
    events: list[Event],
    askfred_id: str,
    settings: Settings,
    site: PreregSource | None,
) -> list[Event]:
    if site is None:
        if not (settings.askfred_email and settings.askfred_password):
            return events
        site = AskFredSite(settings.askfred_email, settings.askfred_password)
    try:
        by_title = site.fetch_preregistrations(askfred_id)
    except RuntimeError:
        return events
    index = {_norm(title): fencers for title, fencers in by_title.items()}
    attached: list[Event] = []
    for event in events:
        fencers = _match_event_fencers(event.name, index)
        attached.append(event.model_copy(update={"fencers": fencers}))
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
