from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fencer_schedules.app import create_app
from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.models import Event, EventResult, Fencer, Tournament
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


def test_home_shows_logo(client: TestClient) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert "/static/favicon.svg" in home.text
    favicon = client.get("/static/favicon.svg")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
    assert "/static/logo.png" in home.text
    logo = client.get("/static/logo.png")
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/png")


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


def _mock_upstream_load(results_for: dict[str, str] | None = None) -> dict:
    """Register the standard AskFRED + USA Fencing mocks.

    Must be called inside an active respx context. Every finished event returns
    an empty results table unless ``results_for`` supplies one, so a page load
    neither retries nor warns about events the test does not care about.
    """
    results_for = results_for or {}
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
    routes = {}
    for event_id in ("72823", "72806", "72829", "99999"):
        routes[event_id] = respx.get(
            "https://member.usafencing.org/details/tournaments/12013/results",
            params={"event_id": event_id},
        ).mock(
            return_value=httpx.Response(
                200, json={"results_table": results_for.get(event_id, "")}
            )
        )
    return routes


@respx.mock
def test_load_trick_shows_club_fencer(client: TestClient) -> None:
    _mock_upstream_load()
    load = client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    assert load.status_code == 200
    assert "Doe, Jordan" in load.text
    assert "8:00 AM" in load.text or "8:00" in load.text
    assert "Elite Fencers Club" in load.text
    assert "Saturday" in load.text
    assert "Cadet Men’s Foil" in load.text or "Cadet Men's Foil" in load.text
    assert "Other events" in load.text
    assert "fencing now" not in load.text.lower()


@respx.mock
def test_finished_event_shows_and_caches_final_results(client: TestClient) -> None:
    results_response = (FIXTURES / "usfa_results_72823.html").read_text().replace(
        "Doe, Jordan", "Doe, Jordan 🇺🇸"
    )
    # Supplied up front: results are fetched during the load and the attempt is
    # remembered, instead of being retried on every page view.
    routes = _mock_upstream_load(results_for={"72823": results_response})
    load = client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    assert load.status_code == 200

    event = client.get("/schedule/events/72823")
    assert event.status_code == 200
    assert routes["72823"].called
    assert "Final results" in event.text
    assert "<details" in event.text
    assert "Doe, Jordan" in event.text
    assert "No result" in event.text
    assert "8" in event.text
    assert "Published by" in event.text
    assert "Final: <strong>8th</strong>" in client.get("/schedule").text

    saved = client.app.state.store.current()
    assert saved is not None
    saved_event = next(item for item in saved.events if item.source_event_id == "72823")
    assert saved_event.results is not None
    assert saved_event.results[0].name == "Doe, Jordan 🇺🇸"


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
    assert "2 fencers" in roster.text
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
def test_results_are_not_refetched_on_every_page_load(client: TestClient) -> None:
    """An event whose results are not published yet must not be re-requested."""
    routes = _mock_upstream_load()
    client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    after_load = routes["72823"].call_count
    assert after_load >= 1, "the first load should ask once"

    client.get("/schedule")
    client.get("/schedule/events/72823")

    assert routes["72823"].call_count == after_load


def test_refresh_preserves_cached_final_results(client: TestClient, monkeypatch) -> None:
    old = Tournament(
        askfred_id="refresh-test",
        name="Refresh Test",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
        events=[
            Event(
                source_event_id="event-1",
                name="Junior Men's Epee",
                day=date(2026, 9, 1),
                fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
                results=[EventResult(place="8", name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )
    client.app.state.store.save(old)
    fresh = old.model_copy(update={
        "events": [old.events[0].model_copy(update={"results": None})]
    })
    monkeypatch.setattr("fencer_schedules.app.load_tournament", lambda *args, **kwargs: fresh)

    response = client.post("/schedule/refresh", follow_redirects=True)

    assert response.status_code == 200
    saved = client.app.state.store.current()
    assert saved is not None
    assert saved.events[0].results is not None
    assert saved.events[0].results[0].place == "8"
    assert "Final: <strong>8th</strong>" in response.text
    assert "Start list updated." in response.text


def test_refresh_keeps_schedule_when_upstream_fails(client: TestClient, monkeypatch) -> None:
    old = Tournament(
        askfred_id="refresh-fail",
        name="Refresh Fail",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
        events=[
            Event(
                source_event_id="event-1",
                name="Junior Men's Epee",
                day=date(2026, 9, 1),
                fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )
    client.app.state.store.save(old)

    def boom(*args, **kwargs):
        raise RuntimeError("AskFRED blocked")

    monkeypatch.setattr("fencer_schedules.app.load_tournament", boom)
    response = client.post("/schedule/refresh", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/schedule?error=refresh")
    page = client.get("/schedule?error=refresh")
    assert page.status_code == 200
    assert "Could not refresh from AskFRED" in page.text
    assert "flash error" in page.text
    saved = client.app.state.store.current()
    assert saved is not None
    assert saved.askfred_id == "refresh-fail"
    assert saved.events[0].fencers[0].name == "Doe, Jordan"


@respx.mock
def test_csv_download(client: TestClient) -> None:
    _mock_upstream_load(
        results_for={"72823": (FIXTURES / "usfa_results_72823.html").read_text()}
    )
    client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    csv = client.get("/schedule.csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert b"fencer,club,final_place" in csv.content
    assert b"Doe, Jordan" in csv.content
    assert b",Elite Fencers Club,8th\r\n" in csv.content


@respx.mock
def test_text_export(client: TestClient) -> None:
    _mock_upstream_load(
        results_for={"72823": (FIXTURES / "usfa_results_72823.html").read_text()}
    )
    client.post(f"/tournaments/{TRICK_ID}/load", follow_redirects=True)
    txt = client.get("/schedule.txt")
    assert txt.status_code == 200
    assert txt.headers["content-type"].startswith("text/plain")
    assert "Doe, Jordan" in txt.text
    assert "Elite Fencers Club" in txt.text
    assert "8th" in txt.text


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
    assert 'type="time"' in resp.text
    assert 'value="09:00"' in resp.text
    assert 'value="21:00"' in resp.text


def test_settings_save_persists_recipient(client: TestClient) -> None:
    resp = client.post(
        "/settings",
        data={"recipient": "frankcng@gmail.com, wife@example.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Saved" in resp.text
    assert client.app.state.store.get_setting("alert_recipient") == "frankcng@gmail.com, wife@example.com"


def test_settings_shows_saved_times(client: TestClient) -> None:
    client.app.state.store.set_setting("alert_times", "07:30,19:00")
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert 'value="07:30"' in resp.text
    assert 'value="19:00"' in resp.text


def test_settings_save_roundtrip_times(client: TestClient) -> None:
    resp = client.post(
        "/settings",
        data={"recipient": "frankcng@gmail.com", "alert_times": ["07:30", "19:00"]},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Saved" in resp.text
    assert client.app.state.store.get_setting("alert_times") == "07:30,19:00"
    assert 'value="07:30"' in resp.text
    assert 'value="19:00"' in resp.text


def test_settings_save_drops_invalid_times(client: TestClient) -> None:
    resp = client.post(
        "/settings",
        data={"recipient": "frankcng@gmail.com", "alert_times": ["bogus", "08:00"]},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert client.app.state.store.get_setting("alert_times") == "08:00"


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

