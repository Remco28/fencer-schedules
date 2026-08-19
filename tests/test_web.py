from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fencer_schedules.app import create_app
from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.sources.askfred import AskFredClient

FIXTURES = Path(__file__).parent / "fixtures"
TRICK_ID = "f4fbfddf-8316-46d2-9392-8a8245059f86"


def _json(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        club_name="Elite Fencers Club",
        club_aliases=["Elite FC"],
        askfred_api_token="x",
        database_path=tmp_path / "t.db",
    )
    askfred = AskFredClient(token="x", today=__import__("datetime").date(2026, 8, 19))
    app = create_app(settings=settings, store=Store(settings.database_path), askfred=askfred)
    return TestClient(app)


@respx.mock
def test_search_trick_lists_trick_or_retreat(client: TestClient) -> None:
    respx.get("https://www.askfred.net/api/v1/tournaments").mock(
        return_value=httpx.Response(200, json=_json("askfred_window.json"))
    )
    response = client.get("/search", params={"q": "trick"})
    assert response.status_code == 200
    assert "Trick or Retreat" in response.text
    assert "Edison" in response.text or "NJ Convention" in response.text
    assert "strip" not in response.text.lower()
    assert "fencing now" not in response.text.lower()


@respx.mock
def test_load_trick_shows_club_fencer(client: TestClient) -> None:
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(200, json=_json("askfred_tournament_trick.json"))
    )
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{TRICK_ID}/events").mock(
        return_value=httpx.Response(200, json=_json("askfred_events_trick.json"))
    )
    respx.get("https://member.usafencing.org/details/tournaments/12013").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "usfa_tournament_12013.html").read_text())
    )
    respx.get("https://member.usafencing.org/details/tournaments/12013/entrants").mock(
        side_effect=lambda request: httpx.Response(
            200,
            json={"entrants_table": "<table></table>"}
            if request.url.params.get("event_id") == "99999"
            else _json("usfa_entrants_72823.json"),
        )
    )
    load = client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    assert load.status_code == 200
    assert "Doe, Jordan" in load.text
    assert "8:00 AM" in load.text or "8:00" in load.text
    assert "Elite Fencers Club" in load.text
    assert "Saturday" in load.text
    assert "Cadet Men’s Foil" in load.text or "Cadet Men's Foil" in load.text
    assert "Other events" in load.text
    assert "fencing now" not in load.text.lower()
    assert "strip" not in load.text.lower()


@respx.mock
def test_track_additional_fencer(client: TestClient) -> None:
    test_load_trick_shows_club_fencer(client)
    added = client.post("/schedule/track", data={"query": "Albrecht"}, follow_redirects=True)
    assert added.status_code == 200
    assert "Albrecht-Smith, Anne" in added.text
    assert "Manchen Academy Of Fencing" in added.text


@respx.mock
def test_event_roster_track_and_untrack(client: TestClient) -> None:
    test_load_trick_shows_club_fencer(client)
    roster = client.get("/schedule/events/72823")
    assert roster.status_code == 200
    assert "Albrecht-Smith, Anne" in roster.text
    assert "Track" in roster.text
    added = client.post(
        "/schedule/track",
        data={
            "name": "Albrecht-Smith, Anne",
            "club": "Manchen Academy Of Fencing",
            "next": "/schedule/events/72823",
        },
        follow_redirects=True,
    )
    assert "Untrack" in added.text
    schedule = client.get("/schedule")
    assert "Albrecht-Smith, Anne" in schedule.text
    client.post(
        "/schedule/untrack",
        data={"name": "Albrecht-Smith, Anne", "club": "Manchen Academy Of Fencing"},
        follow_redirects=True,
    )
    gone = client.get("/schedule")
    assert "Albrecht-Smith, Anne" not in gone.text


@respx.mock
def test_pdf_download(client: TestClient) -> None:
    test_load_trick_shows_club_fencer(client)
    pdf = client.get("/schedule.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
