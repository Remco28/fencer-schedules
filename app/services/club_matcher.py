"""Club matching helpers."""


def match_club(fencer: dict, club_filter: str) -> bool:
    """Check if fencer matches club filter (case-insensitive substring)."""
    if not club_filter:
        return False
    filter_lower = club_filter.lower().strip()

    club1 = (fencer.get("club1") or "").lower()
    club2 = (fencer.get("club2") or "").lower()
    club_names = (fencer.get("clubNames") or "").lower()
    club = (fencer.get("club") or "").lower()
    club_primary = (fencer.get("club_primary") or "").lower()

    return (
        filter_lower in club1
        or filter_lower in club2
        or filter_lower in club_names
        or filter_lower in club
        or filter_lower in club_primary
    )
