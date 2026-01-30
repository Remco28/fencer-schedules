"""Club matching helpers."""
from typing import List, Union


def match_club(fencer: dict, club_filter: Union[str, List[str]]) -> bool:
    """Check if fencer matches ANY club filter (case-insensitive substring)."""
    if not club_filter:
        return False

    # Normalize to list of lower-case strings
    if isinstance(club_filter, str):
        filters = [club_filter.lower().strip()]
    else:
        filters = [f.lower().strip() for f in club_filter if f]

    if not filters:
        return False

    # Get all fencer club fields
    club1 = (fencer.get("club1") or "").lower()
    club2 = (fencer.get("club2") or "").lower()
    club_names = (fencer.get("clubNames") or "").lower()
    club = (fencer.get("club") or "").lower()
    club_primary = (fencer.get("club_primary") or "").lower()
    
    # Check if ANY filter matches ANY club field
    for f in filters:
        if (
            f in club1
            or f in club2
            or f in club_names
            or f in club
            or f in club_primary
        ):
            return True
            
    return False
