"""Fencer validation service for tracked fencer operations."""

import re
from typing import Optional, Tuple
from urllib.parse import unquote


_PROFILE_PATH_PATTERN = re.compile(r"/p/(\d+)(?:/([^/?#]+))?", re.IGNORECASE)


def validate_fencer_id(fencer_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate fencing tracker fencer ID format (numeric).

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not fencer_id:
        return False, "Fencer ID cannot be empty"

    if not fencer_id.isdigit():
        return False, "Fencer ID must be numeric"

    return True, None


def _extract_profile_components(value: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (fencer_id, slug) if a fencingtracker profile path is found."""
    match = _PROFILE_PATH_PATTERN.search(value)
    if not match:
        return None, None

    fencer_id = match.group(1)
    slug = match.group(2)
    if slug:
        slug = slug.strip()
        if not slug:
            slug = None

    return fencer_id, slug


def normalize_tracked_fencer_id(raw_value: str) -> Tuple[Optional[str], Optional[str]]:
    """Normalize raw tracked fencer input into a numeric ID."""
    value = (raw_value or "").strip()

    if not value:
        _, error = validate_fencer_id(value)
        return None, error

    if value.isdigit():
        is_valid, error = validate_fencer_id(value)
        return (value, None) if is_valid else (None, error)

    normalized, _ = _extract_profile_components(value)
    if normalized:
        is_valid, error = validate_fencer_id(normalized)
        return (normalized, None) if is_valid else (None, error)

    lowered = value.lower()
    if (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("www.")
        or lowered.startswith("//")
        or lowered.startswith("fencingtracker.com")
        or lowered.startswith("/p/")
        or lowered.startswith("/")
    ):
        return None, "Could not find a numeric ID in that profile URL"

    return None, "Fencer ID must be numeric"


def extract_profile_slug(raw_value: str) -> Optional[str]:
    """Extract the slug segment from a fencingtracker profile input, if any."""
    if not raw_value:
        return None

    _, slug = _extract_profile_components(raw_value)
    return slug


def derive_display_name_from_slug(slug: Optional[str]) -> Optional[str]:
    """Convert a slug into a human-friendly display name."""
    if not slug:
        return None

    decoded = unquote(slug).replace("_", " ").replace("-", " ").strip()
    if not decoded:
        return None

    tokens = [token for token in decoded.split() if token]
    if not tokens:
        return None

    def _titleize(token: str) -> str:
        if "'" in token:
            parts = token.split("'")
            rebuilt = "'".join(part.capitalize() for part in parts if part)
            if token.startswith("'"):
                rebuilt = "'" + rebuilt
            if token.endswith("'") and not rebuilt.endswith("'"):
                rebuilt = rebuilt + "'"
            return rebuilt
        return token.capitalize()

    return " ".join(_titleize(token) for token in tokens)


def normalize_weapon_filter(weapon_filter: Optional[str]) -> Optional[str]:
    """
    Normalize weapon filter to standard format.

    Accepts: foil, epee, saber (case-insensitive)
    Returns: Comma-separated lowercase string or None (deduplicated)
    """
    if not weapon_filter:
        return None

    # Split on commas and normalize each weapon (using set to deduplicate)
    weapons = set()
    valid_weapons = {"foil", "epee", "saber"}

    for weapon in weapon_filter.split(","):
        weapon = weapon.strip().lower()
        if weapon in valid_weapons:
            weapons.add(weapon)

    if not weapons:
        return None

    # Sort for consistency and join
    return ",".join(sorted(weapons))


def build_fencer_profile_url(fencer_id: str, name_slug: Optional[str] = None) -> str:
    """
    Build fencingtracker profile URL for a fencer.

    Args:
        fencer_id: Numeric fencer ID
        name_slug: Optional name slug (e.g., "Jake-Mann"). If provided, constructs full URL.
                  Can also be display_name which will be converted to slug format.

    Returns:
        Full fencingtracker profile URL
    """
    if name_slug:
        # Convert to URL-safe slug format (replace spaces with dashes, etc.)
        slug = name_slug.strip().replace(" ", "-")
        return f"https://www.fencingtracker.com/p/{fencer_id}/{slug}"

    # Fallback: URL without slug (may result in 404 on fencingtracker)
    return f"https://www.fencingtracker.com/p/{fencer_id}"
