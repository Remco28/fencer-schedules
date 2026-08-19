from __future__ import annotations

import re

from fencer_schedules.config import Settings

_SPACE = re.compile(r"\s+")


def _norm(value: str) -> str:
    return _SPACE.sub(" ", value).strip().casefold()


def is_our_club(club: str, settings: Settings) -> bool:
    needle = _norm(club)
    if not needle:
        return False
    allowed = [_norm(settings.club_name), *(_norm(a) for a in settings.club_aliases)]
    return needle in allowed
