from __future__ import annotations

import re
from datetime import time

import httpx
from bs4 import BeautifulSoup, Tag

from fencer_schedules.models import Fencer

HOST = "https://www.askfred.net"
_SPACE = re.compile(r"\s+")
_CHECKIN = re.compile(
    r"at\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[ap]m)",
    re.I,
)


def parse_preregistrations(html: str) -> dict[str, list[Fencer]]:
    """Map event title -> fencers from the AskFRED preregistrations page."""
    return {title: block[0] for title, block in _parse_cards(html).items()}


def parse_preregistration_clocks(html: str) -> dict[str, time]:
    return {title: clock for title, (_, clock) in _parse_cards(html).items() if clock}


def _parse_cards(html: str) -> dict[str, tuple[list[Fencer], time | None]]:
    soup = BeautifulSoup(html, "html.parser")
    by_event: dict[str, tuple[list[Fencer], time | None]] = {}
    for table in soup.select("table.preregistration-list") or soup.find_all("table"):
        headers = [_norm(cell.get_text()) for cell in table.find_all("th")]
        if "fencer" not in headers:
            continue
        fencer_i = headers.index("fencer")
        club_i = _club_index(headers, table)
        title, clock = _card_meta(table)
        if not title:
            continue
        fencers: list[Fencer] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) <= max(fencer_i, club_i):
                continue
            name = " ".join(cells[fencer_i].get_text(" ", strip=True).split())
            club = " ".join(cells[club_i].get_text(" ", strip=True).split())
            if name:
                fencers.append(Fencer(name=name, club=club))
        by_event[title] = (fencers, clock)
    return by_event


def _club_index(headers: list[str], table: Tag) -> int:
    clubs = [i for i, header in enumerate(headers) if header == "club"]
    if not clubs:
        return 0
    ths = table.find_all("th")
    for index in clubs:
        classes = " ".join(ths[index].get("class") or [])
        if "d-sm-none" not in classes:
            return index
    return clubs[0]


def _card_meta(table: Tag) -> tuple[str, time | None]:
    card = table.find_parent("div", class_="card")
    if card:
        header = card.find("div", class_=re.compile(r"card-header"))
        if header:
            title_el = header.find("span")
            title = " ".join((title_el or header).get_text(" ", strip=True).split())
            # drop trailing check-in line if it landed in the same span
            title = re.split(r"\bCheck-In\b", title, maxsplit=1)[0].strip()
            clock = _parse_checkin(header.get_text(" ", strip=True))
            if title:
                return title, clock
    for node in table.find_all_previous(["h2", "h3", "h4"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text and "preregistration" not in text.casefold():
            return text, None
    return "", None


def _parse_checkin(text: str) -> time | None:
    match = _CHECKIN.search(text)
    if not match:
        return None
    hour = int(match.group("hour")) % 12
    if match.group("ampm").lower() == "pm":
        hour += 12
    return time(hour, int(match.group("minute")))


def _norm(value: str) -> str:
    return _SPACE.sub(" ", value).strip().casefold()


class AskFredSite:
    """Logged-in HTML session for pages the official API does not expose."""

    def __init__(
        self,
        email: str,
        password: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._client = client or httpx.Client(timeout=30.0, follow_redirects=True)
        self._owns = client is None
        self._authed = False
        self._html_cache: dict[str, str] = {}

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def login(self) -> None:
        page = self._client.get(f"{HOST}/users/sign_in")
        page.raise_for_status()
        if "bot-challenge" in str(page.url) or "verify you are human" in page.text.casefold():
            raise RuntimeError("AskFRED login hit a bot challenge")
        soup = BeautifulSoup(page.text, "html.parser")
        token_el = soup.select_one('form[action="/users/sign_in"] input[name="authenticity_token"]')
        token = token_el.get("value") if token_el else ""
        resp = self._client.post(
            f"{HOST}/users/sign_in",
            data={
                "authenticity_token": token,
                "user[email]": self._email,
                "user[password]": self._password,
            },
        )
        resp.raise_for_status()
        if "bot-challenge" in str(resp.url):
            raise RuntimeError("AskFRED login hit a bot challenge")
        if "/users/sign_in" in str(resp.url):
            raise RuntimeError("AskFRED login failed")
        self._authed = True

    def fetch_preregistrations(self, tournament_id: str) -> dict[str, list[Fencer]]:
        return self._load(tournament_id)[0]

    def fetch_preregistration_clocks(self, tournament_id: str) -> dict[str, time]:
        return self._load(tournament_id)[1]

    def _load(self, tournament_id: str) -> tuple[dict[str, list[Fencer]], dict[str, time]]:
        html = self._html(tournament_id)
        return parse_preregistrations(html), parse_preregistration_clocks(html)

    def _html(self, tournament_id: str) -> str:
        cached = self._html_cache.get(tournament_id)
        if cached is not None:
            return cached
        if not self._authed:
            self.login()
        resp = self._client.get(f"{HOST}/tournaments/{tournament_id}/preregistrations")
        resp.raise_for_status()
        if "bot-challenge" in str(resp.url) or "verify you are human" in resp.text.casefold():
            raise RuntimeError("AskFRED preregistrations hit a bot challenge")
        self._html_cache[tournament_id] = resp.text
        return resp.text
