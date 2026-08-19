from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from fencer_schedules.models import Event, Tournament

BASE = "https://www.askfred.net/api/v1"
USFA_ID = re.compile(r"/details/tournaments/(\d+)")


def usfa_id_from_registration_url(url: str | None) -> str | None:
    if not url:
        return None
    match = USFA_ID.search(url)
    return match.group(1) if match else None


class AskFredClient:
    def __init__(
        self,
        token: str,
        client: httpx.Client | None = None,
        today: date | None = None,
        window_days: int = 45,
    ) -> None:
        self._token = token
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self._today = today or date.today()
        self._window_days = window_days
        self._window_cache: list[Tournament] | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._client.get(
            f"{BASE}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )
        if resp.status_code == 429:
            raise RuntimeError("AskFRED rate limited")
        resp.raise_for_status()
        return resp.json()

    def fetch_tournament(self, askfred_id: str) -> Tournament:
        payload = self._get(f"/tournaments/{askfred_id}")
        return self._tournament_from_item(payload["data"])

    def fetch_events(self, askfred_id: str) -> list[Event]:
        events: list[Event] = []
        page = 1
        while True:
            payload = self._get(
                f"/tournaments/{askfred_id}/events",
                {"per_page": 50, "page": page},
            )
            for item in payload.get("data") or []:
                events.append(self._event_from_item(item))
            meta = payload.get("metadata") or {}
            last = int(meta.get("last_page") or 1)
            if page >= last:
                break
            page += 1
        return events

    def search(self, query: str) -> list[Tournament]:
        needle = query.strip().casefold()
        if not needle:
            return []
        return [t for t in self._upcoming_window() if needle in t.name.casefold()]

    def _upcoming_window(self) -> list[Tournament]:
        if self._window_cache is not None:
            return self._window_cache
        start = self._today.isoformat()
        end = (self._today + timedelta(days=self._window_days)).isoformat()
        found: list[Tournament] = []
        page = 1
        while True:
            payload = self._get(
                "/tournaments",
                {
                    "start_date_gteq": start,
                    "end_date_lteq": end,
                    "per_page": 50,
                    "page": page,
                },
            )
            for item in payload.get("data") or []:
                found.append(self._tournament_from_item(item))
            meta = payload.get("metadata") or {}
            last = int(meta.get("last_page") or 1)
            if page >= last:
                break
            page += 1
        self._window_cache = found
        return found

    def _tournament_from_item(self, item: dict[str, Any]) -> Tournament:
        attrs = item.get("attributes") or {}
        return Tournament(
            askfred_id=item["id"],
            name=attrs["name"],
            start_date=date.fromisoformat(attrs["start_date"]),
            end_date=date.fromisoformat(attrs["end_date"]),
            usfa_id=usfa_id_from_registration_url(attrs.get("registration_url")),
            venue=attrs.get("venue_name"),
        )

    def _event_from_item(self, item: dict[str, Any]) -> Event:
        attrs = item.get("attributes") or {}
        clock = None
        day = date.fromisoformat("1970-01-01")
        raw = attrs.get("close_of_registration")
        if raw:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            clock = dt.timetz().replace(tzinfo=None)
            day = dt.date()
        return Event(
            source_event_id=item["id"],
            name=attrs.get("full_name") or attrs.get("short_name") or "Event",
            day=day,
            clock=clock,
            clock_label=None,
        )
