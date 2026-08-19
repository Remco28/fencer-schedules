from __future__ import annotations

import re
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from fencer_schedules.models import Event, Fencer

USFA_HOST = "https://member.usafencing.org"
_MEMBERSHIP = re.compile(r"#(\d+)")


def parse_tournament_events(html: str, year: int | None = None) -> list[Event]:
    year = year or date.today().year
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id="events-by-day") or soup
    events: list[Event] = []
    current_day: date | None = None
    for node in root.find_all(True):
        classes = node.get("class") or []
        if "event-by-day-date" in classes:
            text = node.get_text(" ", strip=True)
            current_day = _parse_day(text, year)
            continue
        event_id = node.get("data-event_id")
        if not event_id or node.name != "div":
            continue
        name_el = node.find(class_="name")
        name = name_el.get_text(" ", strip=True) if name_el else "Event"
        events.append(
            Event(
                source_event_id=str(event_id),
                name=name,
                day=current_day or date.min,
            )
        )
    return events


def parse_entrants_table(html: str) -> list[Fencer]:
    soup = BeautifulSoup(html, "html.parser")
    fencers: list[Fencer] = []
    for row in soup.find_all("tr"):
        club = row.get("data-club")
        if not club:
            continue
        heading = row.find("h4")
        name = heading.get_text(" ", strip=True) if heading else ""
        if not name:
            continue
        membership = None
        blob = row.get_text(" ", strip=True)
        match = _MEMBERSHIP.search(blob)
        if match:
            membership = match.group(1)
        fencers.append(Fencer(name=name, club=club, membership_id=membership))
    return fencers


def _parse_day(text: str, year: int) -> date | None:
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", text.strip())
    for fmt in ("%B %d", "%b %d"):
        try:
            return datetime.strptime(f"{cleaned} {year}", f"{fmt} %Y").date()
        except ValueError:
            continue
    return None


class UsfaClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)
        self._owns = client is None

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def fetch_events(self, usfa_id: str, year: int | None = None) -> list[Event]:
        resp = self._client.get(f"{USFA_HOST}/details/tournaments/{usfa_id}")
        resp.raise_for_status()
        return parse_tournament_events(resp.text, year=year)

    def fetch_entrants(self, usfa_id: str, event_id: str) -> list[Fencer]:
        resp = self._client.get(
            f"{USFA_HOST}/details/tournaments/{usfa_id}/entrants",
            params={"event_id": event_id},
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{USFA_HOST}/details/tournaments/{usfa_id}",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        return parse_entrants_table(payload.get("entrants_table") or "")
