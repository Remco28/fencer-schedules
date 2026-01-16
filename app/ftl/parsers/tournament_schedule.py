"""Parse FencingTimeLive tournament schedule page."""
from bs4 import BeautifulSoup
import re
from typing import Optional


_EVENT_ID_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")


def _normalize_weapon(name: str) -> Optional[str]:
    normalized = name.lower().replace("\u00e9", "e").replace("\u00e8", "e")
    if "epee" in normalized:
        return "Epee"
    if "foil" in normalized:
        return "Foil"
    if "sabre" in normalized or "saber" in normalized:
        return "Saber"
    return None


def _extract_event_id(row_id: str, data_href: str) -> Optional[str]:
    if row_id and row_id.startswith("ev_"):
        candidate = row_id.replace("ev_", "")
        if _EVENT_ID_PATTERN.match(candidate):
            return candidate

    if data_href:
        match = re.search(r"/events/view/([A-Fa-f0-9]{32})", data_href)
        if match:
            return match.group(1)

    return None


def parse_tournament_schedule(html: str) -> dict:
    """
    Parse tournament schedule page HTML.

    Returns:
        {
            "tournament_name": str,
            "events": [
                {
                    "event_id": str (32-char hex),
                    "name": str,
                    "date": str,
                    "start_time": str,
                    "weapon": str | None (Epee, Foil, Saber),
                    "status": str,
                }
            ]
        }
    """
    if not html:
        raise ValueError("Empty tournament schedule HTML")

    soup = BeautifulSoup(html, "html.parser")

    tournament_name = None
    name_div = soup.select_one(".tournName")
    if name_div:
        tournament_name = name_div.get_text(strip=True)

    if not tournament_name and soup.title and soup.title.string:
        tournament_name = soup.title.string.strip()

    tournament_name = tournament_name or "Unknown Tournament"

    events = []
    current_date = ""

    for node in soup.find_all(["h5", "tr"]):
        if node.name == "h5":
            current_date = node.get_text(" ", strip=True)
            continue

        row_id = node.get("id", "")
        data_href = node.get("data-href", "")
        event_id = _extract_event_id(row_id, data_href)
        if not event_id:
            continue

        cells = node.find_all("td")
        start_time = cells[0].get_text(strip=True) if len(cells) > 0 else ""
        name_cell = cells[1] if len(cells) > 1 else None
        status = cells[2].get_text(strip=True) if len(cells) > 2 else ""

        name = ""
        if name_cell:
            strong = name_cell.find("strong")
            if strong:
                name = strong.get_text(strip=True)
            else:
                name = name_cell.get_text(" ", strip=True)

        events.append({
            "event_id": event_id,
            "name": name,
            "date": current_date,
            "start_time": start_time,
            "weapon": _normalize_weapon(name),
            "status": status,
        })

    return {"tournament_name": tournament_name, "events": events}
