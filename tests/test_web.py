from __future__ import annotations

import json
from pathlib import Path

from datetime import date

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fencer_schedules.app import create_app
from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.models import Event, Fencer, Tournament
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


@respx.mock
def test_csv_download(client: TestClient) -> None:
    test_load_trick_shows_club_fencer(client)
    csv = client.get("/schedule.csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert b"fencer,club" in csv.content
    assert b"Doe, Jordan" in csv.content


@respx.mock
def test_text_export(client: TestClient) -> None:
    test_load_trick_shows_club_fencer(client)
    txt = client.get("/schedule.txt")
    assert txt.status_code == 200
    assert txt.headers["content-type"].startswith("text/plain")
    assert "Doe, Jordan" in txt.text
    assert "Elite Fencers Club" in txt.text


def test_switch_between_saved_tournaments(client: TestClient) -> None:
    store = client.app.state.store
    store.save(
        Tournament(
            askfred_id="one",
            name="First Cup",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            events=[
                Event(
                    source_event_id="e1",
                    name="Senior Mixed Epee",
                    day=date(2026, 9, 1),
                    fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
                )
            ],
        )
    )
    store.save(
        Tournament(
            askfred_id="two",
            name="Second Cup",
            start_date=date(2026, 9, 2),
            end_date=date(2026, 9, 2),
        )
    )
    opened = client.post("/tournaments/one/open", follow_redirects=True)
    assert opened.status_code == 200
    assert "First Cup" in opened.text
    assert "Doe, Jordan" in opened.text
    home = client.get("/")
    assert "First Cup" in home.text
    assert "Second Cup" in home.text
    client.post("/tournaments/two/remove", follow_redirects=True)
    home = client.get("/")
    assert "Second Cup" not in home.text
    assert "Doe, Jordan" in client.get("/schedule").text


def test_settings_page_shows_default_recipient(client: TestClient) -> None:
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "frankcng@gmail.com" in resp.text


def test_settings_save_persists_recipient(client: TestClient) -> None:
    resp = client.post(
        "/settings",
        data={"recipient": "frankcng@gmail.com, wife@example.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Saved" in resp.text
    assert client.app.state.store.get_setting("alert_recipient") == "frankcng@gmail.com, wife@example.com"


def test_club_watch_toggle_on_and_off(client: TestClient) -> None:
    store = client.app.state.store
    store.save(
        Tournament(
            askfred_id="one",
            name="First Cup",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            events=[
                Event(
                    source_event_id="e1",
                    name="Senior Mixed Epee",
                    day=date(2026, 9, 1),
                    fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
                )
            ],
        )
    )
    resp = client.post("/schedule/watch", data={"next": "/schedule"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Watching — Elite FC only" in resp.text
    assert store.watch_for("one", None, "club") is not None
    # toggle off
    resp = client.post("/schedule/watch", data={"next": "/schedule"}, follow_redirects=True)
    assert "Watch for new Elite FC fencers" in resp.text
    assert store.watch_for("one", None, "club") is None


def test_event_watch_toggle(client: TestClient) -> None:
    store = client.app.state.store
    store.save(
        Tournament(
            askfred_id="one",
            name="First Cup",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            events=[
                Event(
                    source_event_id="e1",
                    name="Senior Mixed Epee",
                    day=date(2026, 9, 1),
                    fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
                )
            ],
        )
    )
    resp = client.post(
        "/schedule/events/e1/watch",
        data={"next": "/schedule/events/e1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Watching this event — anyone" in resp.text
    assert store.watch_for("one", "e1", "all") is not None

