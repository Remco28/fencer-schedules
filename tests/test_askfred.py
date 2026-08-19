from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import respx

from fencer_schedules.sources.askfred import AskFredClient, usfa_id_from_registration_url

FIXTURES = Path(__file__).parent / "fixtures"
TRICK_ID = "f4fbfddf-8316-46d2-9392-8a8245059f86"


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_usfa_id_from_member_url() -> None:
    assert (
        usfa_id_from_registration_url(
            "https://member.usafencing.org/details/tournaments/12013"
        )
        == "12013"
    )


def test_local_preregister_url_has_no_usfa_id() -> None:
    assert (
        usfa_id_from_registration_url(
            "https://www.askfred.net/tournaments/07060a1f-1e22-4db1-b6f6-a7f0d956d877/preregister"
        )
        is None
    )


@respx.mock
def test_fetch_tournament_reads_usfa_registration_url() -> None:
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(200, json=_json("askfred_tournament_trick.json"))
    )
    tournament = AskFredClient(token="x").fetch_tournament(TRICK_ID)
    assert tournament.name == "Trick or Retreat ROC / RJCC"
    assert tournament.usfa_id == "12013"
    assert tournament.venue == "NJ Convention & Exposition Center"


@respx.mock
def test_search_filters_upcoming_window() -> None:
    respx.get("https://www.askfred.net/api/v1/tournaments").mock(
        return_value=httpx.Response(200, json=_json("askfred_window.json"))
    )
    client = AskFredClient(token="x", today=date(2026, 8, 19))
    hits = client.search("trick")
    assert [h.askfred_id for h in hits] == [TRICK_ID]
    assert client.search("") == []


@respx.mock
def test_fetch_events_maps_close_of_registration() -> None:
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{TRICK_ID}/events").mock(
        return_value=httpx.Response(200, json=_json("askfred_events_trick.json"))
    )
    events = AskFredClient(token="x").fetch_events(TRICK_ID)
    assert len(events) == 2
    assert events[0].clock is not None
    assert events[0].name.startswith("Division IA")
