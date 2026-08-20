from __future__ import annotations

import re
from collections import defaultdict

import httpx
from bs4 import BeautifulSoup, Tag

from fencer_schedules.models import Fencer

HOST = "https://www.askfred.net"
_SPACE = re.compile(r"\s+")


def parse_preregistrations(html: str) -> dict[str, list[Fencer]]:
    """Map event title -> fencers from the AskFRED preregistrations page."""
    soup = BeautifulSoup(html, "html.parser")
    by_event: dict[str, list[Fencer]] = defaultdict(list)
    for table in soup.find_all("table"):
        headers = [_norm(cell.get_text()) for cell in table.find_all("th")]
        if "fencer" not in headers or "club" not in headers:
            continue
        fencer_i = headers.index("fencer")
        club_i = headers.index("club")
        title = _event_title_before(table)
        if not title:
            continue
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) <= max(fencer_i, club_i):
                continue
            name = " ".join(cells[fencer_i].get_text(" ", strip=True).split())
            club = " ".join(cells[club_i].get_text(" ", strip=True).split())
            if name:
                by_event[title].append(Fencer(name=name, club=club))
    return dict(by_event)


def _event_title_before(table: Tag) -> str:
    for node in table.find_all_previous(["h1", "h2", "h3", "h4", "caption"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text and "preregistration" not in text.casefold():
            return text
    heading = table.find_previous(class_=re.compile(r"event", re.I))
    if heading:
        return " ".join(heading.get_text(" ", strip=True).split())
    return ""


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
        if not self._authed:
            self.login()
        resp = self._client.get(f"{HOST}/tournaments/{tournament_id}/preregistrations")
        resp.raise_for_status()
        if "bot-challenge" in str(resp.url) or "verify you are human" in resp.text.casefold():
            raise RuntimeError("AskFRED preregistrations hit a bot challenge")
        return parse_preregistrations(resp.text)
