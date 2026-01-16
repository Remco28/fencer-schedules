"""Discover pool and DE round IDs from event page."""
import re
from bs4 import BeautifulSoup
from typing import Optional


_POOL_PATTERN = re.compile(r"/pools/scores/[^/]+/([A-Fa-f0-9]{32})")
_DE_PATTERN = re.compile(r"/tableaus/scores/[^/]+/([A-Fa-f0-9]{32})")


def _find_round_id(hrefs: list[str], pattern: re.Pattern[str]) -> Optional[str]:
    for href in hrefs:
        match = pattern.search(href)
        if match:
            return match.group(1)
    return None


def parse_event_rounds(html: str) -> dict:
    """
    Extract pool and DE round IDs from event page navigation.

    Returns:
        {
            "pool_round_id": str | None,
            "de_round_id": str | None,
        }
    """
    if not html:
        raise ValueError("Empty event page HTML")

    soup = BeautifulSoup(html, "html.parser")
    hrefs = [anchor["href"] for anchor in soup.find_all("a", href=True)]

    return {
        "pool_round_id": _find_round_id(hrefs, _POOL_PATTERN),
        "de_round_id": _find_round_id(hrefs, _DE_PATTERN),
    }
