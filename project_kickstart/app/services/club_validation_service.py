"""Utilities for validating fencing tracker club URLs."""

import logging
from typing import Optional, Tuple
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from .scraper_service import normalize_club_url


logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_club_name(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract the club name from the page."""
    for selector in ["h1", "title", "h2"]:
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
    return None


def validate_club_url(club_url: str, timeout: int = 10) -> Tuple[str, str]:
    """Validate the club URL and return normalized URL and club name."""
    normalized_url = normalize_club_url(club_url)

    try:
        response = requests.get(normalized_url, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Failed to reach club URL %s: %s", normalized_url, exc)
        raise ValueError("Unable to reach club page") from exc

    if response.status_code >= 400:
        raise ValueError(f"Unable to reach club page (status code {response.status_code})")

    soup = BeautifulSoup(response.content, "html.parser")
    fallback_name = unquote(normalized_url.rstrip("/").split("/")[-2])
    club_name = _extract_club_name(soup) or fallback_name

    return normalized_url, club_name
