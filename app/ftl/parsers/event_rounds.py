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


def _find_round_ids(hrefs: list[str], pattern: re.Pattern[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for href in hrefs:
        match = pattern.search(href)
        if match:
            round_id = match.group(1)
            if round_id not in seen:
                seen.add(round_id)
                results.append(round_id)
    return results


def parse_event_rounds(html: str) -> dict:
    """
    Extract pool and DE round IDs from event page navigation.

    Returns:
        {
            "pool_round_id": str | None,
            "de_round_id": str | None,
            "pool_round_ids": list[str],
            "de_round_ids": list[str],
        }
    """
    if not html:
        raise ValueError("Empty event page HTML")

    soup = BeautifulSoup(html, "html.parser")
    hrefs = [anchor["href"] for anchor in soup.find_all("a", href=True)]

    pool_round_ids = _find_round_ids(hrefs, _POOL_PATTERN)
    de_round_ids = _find_round_ids(hrefs, _DE_PATTERN)

    return {
        "pool_round_id": pool_round_ids[0] if pool_round_ids else None,
        "de_round_id": de_round_ids[0] if de_round_ids else None,
        "pool_round_ids": pool_round_ids,
        "de_round_ids": de_round_ids,
    }
