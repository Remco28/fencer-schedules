from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from fencer_schedules.config import Settings
from fencer_schedules.fencing_api import ApiUnavailable, FencingApi, StillLoading
from fencer_schedules.load import load_tournament

FIXTURES = Path(__file__).parent / "fixtures" / "api"
API = "http://api.test"
LOCAL_ID = "07060a1f-1e22-4db1-b6f6-a7f0d956d877"
TRICK_ID = "f4fbfddf-8316-46d2-9392-8a8245059f86"
SETTINGS = Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])


def _api(name: str):
    return json.loads((FIXTURES / name).read_text())


def _stored(body: dict) -> dict:
    return {"source": "live", "fetched_at": "2026-08-19T12:00:00Z", "stale": False, **body}


LOCAL_TOURNAMENT = _stored({
    "tournament": {"askfred_id": LOCAL_ID, "name": "Wanglei Summer Cup", "start_date": "2026-08-29",
                   "end_date": "2026-08-29", "usfa_id": None, "venue": "Wanglei"},
    "items": [
        {"askfred_event_id": "e1", "name": "Y14 Mixed Epee", "day": "2026-08-29", "clock": None},
        {"askfred_event_id": "e2", "name": "Senior Mixed Epee", "day": "2026-08-29", "clock": "13:00"},
    ],
})


def _client(wait_s: float = 3) -> FencingApi:
    return FencingApi(API, "fapi_test", wait_s=wait_s)


@respx.mock
def test_local_load_uses_registration_names_and_checkin_clocks() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{LOCAL_ID}").mock(return_value=httpx.Response(200, json=LOCAL_TOURNAMENT))
    respx.get(f"{API}/v1/askfred/tournaments/{LOCAL_ID}/entries").mock(
        return_value=httpx.Response(200, json=_api("wanglei_entries.json")))
    tournament = load_tournament(LOCAL_ID, SETTINGS, api=_client())
    assert tournament.names_available
    y14 = next(e for e in tournament.events if e.name == "Y14 Mixed Epee")
    assert y14.fencers[0].name == "Anderson, Connor"
    assert y14.clock is not None and (y14.clock.hour, y14.clock.minute) == (9, 30)  # from check-in
    senior = next(e for e in tournament.events if e.name == "Senior Mixed Epee")
    assert (senior.clock.hour, senior.clock.minute) == (13, 0)  # the event's own clock wins


@respx.mock
def test_local_load_keeps_events_when_registrations_fail() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{LOCAL_ID}").mock(return_value=httpx.Response(200, json=LOCAL_TOURNAMENT))
    respx.get(f"{API}/v1/askfred/tournaments/{LOCAL_ID}/entries").mock(
        return_value=httpx.Response(502, json={"error": "scrape_failed", "detail": "LoginFailed: AskFRED login failed"}))
    tournament = load_tournament(LOCAL_ID, SETTINGS, api=_client())
    assert [e.name for e in tournament.events] == ["Y14 Mixed Epee", "Senior Mixed Epee"]
    assert all(e.fencers == [] for e in tournament.events)
    assert not tournament.names_available


@respx.mock
def test_regional_load_takes_every_event_from_usa_fencing_in_one_request() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(200, json=_api("trick_tournament.json")))
    entries = respx.get(f"{API}/v1/usfa/tournaments/12013/entries").mock(
        return_value=httpx.Response(200, json=_api("trick_usfa_entries.json")))
    tournament = load_tournament(TRICK_ID, SETTINGS, api=_client())
    assert entries.call_count == 1
    assert tournament.usfa_id == "12013" and len(tournament.events) == 4
    junior = next(e for e in tournament.events if e.source_event_id == "72823")
    assert junior.day.isoformat() == "2026-08-22" and (junior.clock.hour, junior.clock.minute) == (8, 0)
    assert junior.clock_label is None
    assert any(f.name == "Doe, Jordan" and f.club == "Elite Fencers Club" for f in junior.fencers)


@respx.mock
def test_a_slow_first_load_waits_on_the_job_then_returns() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(200, json=_api("trick_tournament.json")))
    respx.get(f"{API}/v1/usfa/tournaments/12013/entries").mock(
        return_value=httpx.Response(202, json={"fetched_at": None, "status": "processing", "job_id": 5}))
    polls = iter([{"id": 5, "status": "running"},
                  {"id": 5, "status": "done", "result": _api("trick_usfa_entries.json")}])
    respx.get(f"{API}/v1/jobs/5").mock(side_effect=lambda request: httpx.Response(200, json=next(polls)))
    tournament = load_tournament(TRICK_ID, SETTINGS, api=_client(wait_s=10))
    assert len(tournament.events) == 4


@respx.mock
def test_still_loading_when_the_wait_runs_out() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(200, json=_api("trick_tournament.json")))
    respx.get(f"{API}/v1/usfa/tournaments/12013/entries").mock(
        return_value=httpx.Response(202, json={"fetched_at": None, "status": "processing", "job_id": 6}))
    respx.get(f"{API}/v1/jobs/6").mock(return_value=httpx.Response(200, json={"id": 6, "status": "running"}))
    with pytest.raises(StillLoading):
        load_tournament(TRICK_ID, SETTINGS, api=_client(wait_s=2))


@respx.mock
def test_api_down_or_key_rejected_is_unavailable_not_silent() -> None:
    respx.get(f"{API}/v1/askfred/tournaments/{TRICK_ID}").mock(
        return_value=httpx.Response(401, json={"error": "bad_key", "detail": "Unknown API key."}))
    with pytest.raises(ApiUnavailable, match="401"):
        load_tournament(TRICK_ID, SETTINGS, api=_client())
    respx.get(f"{API}/v1/askfred/tournaments/{TRICK_ID}").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ApiUnavailable, match="unreachable"):
        load_tournament(TRICK_ID, SETTINGS, api=_client())
