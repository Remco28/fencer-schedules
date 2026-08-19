from __future__ import annotations

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Tournament
from fencer_schedules.sources.askfred import AskFredClient
from fencer_schedules.sources.usfa import UsfaClient


def load_tournament(
    askfred_id: str,
    settings: Settings,
    askfred: AskFredClient | None = None,
    usfa: UsfaClient | None = None,
) -> Tournament:
    askfred = askfred or AskFredClient(settings.askfred_api_token)
    tournament = askfred.fetch_tournament(askfred_id)
    askfred_events = askfred.fetch_events(askfred_id)
    if not tournament.usfa_id:
        tournament.events = askfred_events
        tournament.names_available = False
        return tournament

    usfa = usfa or UsfaClient()
    usfa_events = usfa.fetch_events(tournament.usfa_id, year=tournament.start_date.year)
    clocks = _clocks_by_name(askfred_events)
    filled: list[Event] = []
    for event in usfa_events:
        entrants = usfa.fetch_entrants(tournament.usfa_id, event.source_event_id)
        clock, label = clocks.get(_norm(event.name), (event.clock, event.clock_label))
        filled.append(
            event.model_copy(
                update={"fencers": entrants, "clock": clock, "clock_label": label}
            )
        )
    tournament.events = filled
    tournament.names_available = True
    return tournament


def _norm(name: str) -> str:
    return " ".join(name.replace("’", "'").casefold().split())


def _clocks_by_name(events: list[Event]) -> dict[str, tuple]:
    return {_norm(event.name): (event.clock, event.clock_label) for event in events}
