"""fencing-api client: every tournament, entrant and result comes from here.

fencing-api (the home server's shared scraper, ~/Projects/fencing-api) reads
AskFRED and USA Fencing once, keeps what it read, and serves every app. This
app has no scrapers of its own: if data is wrong or missing, fix fencing-api.
"""
from __future__ import annotations

import time as _time
from datetime import date, time
from typing import Any

import httpx

from fencer_schedules.models import UNKNOWN_DAY, Event, EventResult, Fencer, Tournament

POLL_S = 1.5


class StillLoading(Exception):
    """fencing-api is still reading the site; the data will be there shortly."""


class ApiUnavailable(Exception):
    """fencing-api is down, rejected our key, or failed itself."""


class NotAvailable(Exception):
    """The site has no such page (e.g. results not posted)."""


class FencingApi:
    def __init__(self, base_url: str, key: str, client: httpx.Client | None = None, wait_s: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = key
        self.wait_s = wait_s
        self._client = client or httpx.Client(timeout=30.0)
        self._owns = client is None

    def close(self) -> None:
        if self._owns:
            self._client.close()

    # -- transport -----------------------------------------------------------
    def _call(self, path: str, params: dict[str, Any] | None, give_up_at: float) -> dict[str, Any]:
        timeout = max(1.0, give_up_at - _time.monotonic())
        try:
            resp = self._client.get(
                f"{self.base_url}{path}", params=params, timeout=timeout,
                headers={"X-API-Key": self.key, "Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise StillLoading("fencing-api is still reading the site") from exc
        except httpx.HTTPError as exc:
            raise ApiUnavailable(f"fencing-api unreachable: {exc}") from exc
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code in (200, 202):
            return body
        detail = body.get("detail") or resp.status_code
        if resp.status_code == 404 and body.get("error") == "scrape_failed":
            raise NotAvailable(str(detail))
        if resp.status_code == 429:
            raise StillLoading("fencing-api is busy (rate limited)")
        if resp.status_code in (401, 403) or (resp.status_code >= 500 and body.get("error") != "scrape_failed"):
            raise ApiUnavailable(f"fencing-api {resp.status_code}: {detail}")
        raise ApiUnavailable(f"fencing-api could not read the site: {detail}")

    def get(self, path: str, params: dict[str, Any] | None = None, wait_s: float | None = None) -> dict[str, Any]:
        """A live read: fresh stored data at once, else wait for the scrape (polling its job)."""
        give_up_at = _time.monotonic() + (self.wait_s if wait_s is None else wait_s)
        body = self._call(path, {**(params or {}), "live": "true"}, give_up_at)
        if body.get("fetched_at"):
            return body
        job_id = body.get("job_id")
        if not job_id:
            raise ApiUnavailable("fencing-api returned no data")
        while _time.monotonic() < give_up_at:
            _time.sleep(POLL_S)
            job = self._call(f"/v1/jobs/{job_id}", None, give_up_at)
            if job.get("status") in ("done", "failed"):
                result = job.get("result") or {}
                if result.get("fetched_at"):
                    return result
                if str(job.get("error") or "").startswith("not_available"):
                    raise NotAvailable(job["error"])
                raise ApiUnavailable(f"fencing-api could not read the site: {job.get('error')}")
        raise StillLoading("fencing-api is still reading the site")

    # -- what this app needs -------------------------------------------------
    def search(self, query: str) -> list[Tournament]:
        body = self.get("/v1/tournaments", {"q": query, "period": "upcoming"})
        return [t for t in (_tournament(item) for item in body.get("items") or []) if t]

    def tournament(self, askfred_id: str, wait_s: float | None = None) -> tuple[Tournament, list[Event]]:
        body = self.get(f"/v1/askfred/tournaments/{askfred_id}", wait_s=wait_s)
        tournament = _tournament(body.get("tournament") or {})
        if tournament is None:
            raise ApiUnavailable(f"fencing-api returned no tournament for {askfred_id}")
        events = [
            _event(item.get("askfred_event_id"), item)
            for item in body.get("items") or []
        ]
        return tournament, events

    def usfa_tournament_entries(self, usfa_id: str, wait_s: float | None = None) -> list[Event]:
        """Every event of a USA Fencing tournament with its entrants."""
        body = self.get(f"/v1/usfa/tournaments/{usfa_id}/entries", wait_s=wait_s)
        return [
            _event(item.get("usfa_event_id"), item).model_copy(update={
                "fencers": [_fencer(row) for row in item.get("entries") or []],
            })
            for item in body.get("items") or []
        ]

    def askfred_entries(self, askfred_id: str, wait_s: float | None = None) -> list[tuple[str, time | None, list[Fencer]]]:
        """(event title, check-in clock, entrants) from AskFRED preregistrations."""
        body = self.get(f"/v1/askfred/tournaments/{askfred_id}/entries", wait_s=wait_s)
        return [
            (item.get("event_name") or "", _clock(item.get("check_in")), [_fencer(row) for row in item.get("entries") or []])
            for item in body.get("items") or []
        ]

    def usfa_results(self, usfa_id: str, event_id: str) -> list[EventResult]:
        try:
            body = self.get(f"/v1/usfa/tournaments/{usfa_id}/events/{event_id}/results")
        except NotAvailable:
            return []
        return [
            EventResult(
                place=str(row.get("place_label") or row.get("place") or ""),
                name=row.get("name") or "",
                club=row.get("club") or "",
                membership_id=row.get("membership_id"),
            )
            for row in body.get("items") or []
            if row.get("name")
        ]


def _clock(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hour, minute = value.split(":")[:2]
        return time(int(hour), int(minute))
    except ValueError:
        return None


def _tournament(item: dict[str, Any]) -> Tournament | None:
    if not item.get("askfred_id") or not item.get("start_date"):
        return None
    start = date.fromisoformat(item["start_date"])
    return Tournament(
        askfred_id=item["askfred_id"],
        name=item.get("name") or "",
        start_date=start,
        end_date=date.fromisoformat(item["end_date"]) if item.get("end_date") else start,
        usfa_id=item.get("usfa_id"),
        venue=item.get("venue"),
    )


def _event(event_id: Any, item: dict[str, Any]) -> Event:
    day = item.get("day")
    return Event(
        source_event_id=str(event_id),
        name=item.get("name") or "Event",
        # The source sometimes publishes no day; never invent one.
        day=date.fromisoformat(day) if day else UNKNOWN_DAY,
        day_unknown=not day,
        clock=_clock(item.get("clock")),
        # Shown as a plain time, as before (USFA's card time is the event start).
        clock_label=None,
    )


def _fencer(row: dict[str, Any]) -> Fencer:
    return Fencer(name=row.get("name") or "", club=row.get("club") or "", membership_id=row.get("membership_id"))
