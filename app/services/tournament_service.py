"""Tournament fencer status orchestration."""
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Optional, Iterable

from app.ftl.client import fetch_pools_bundle, fetch_tableau_raw, FTLHTTPError, FTLParseError
from app.ftl.parsers.de_tableau import parse_de_tableau
from app.services.club_matcher import match_club

logger = logging.getLogger(__name__)


@dataclass
class FencerStatus:
    """Status of a single fencer in a tournament."""
    name: str
    event_id: str
    event_name: str
    weapon: Optional[str]

    # Location
    pool_number: Optional[int] = None
    strip: Optional[str] = None
    de_round: Optional[str] = None  # "64", "32", "16", "QF", "SF", "F"

    # Status
    activity: str = "unknown"  # "active", "waiting", "finished"
    phase: str = "unknown"  # "pools", "de", "complete"
    result: Optional[str] = None  # "Advanced", "Eliminated", "3rd Place", etc.

    # Metadata
    last_updated: str = ""
    error: Optional[str] = None


_ROUND_ORDER = ["128", "64", "32", "16", "8", "QF", "SF", "F"]
_NEXT_ROUND_LABELS = {
    "128": "Table of 64",
    "64": "Table of 32",
    "32": "Table of 16",
    "16": "Table of 8",
    "8": "Quarterfinal",
    "QF": "Semifinal",
    "SF": "Final",
}


def _activity_rank(activity: str) -> int:
    return {"finished": 3, "active": 2, "waiting": 1}.get(activity, 0)


def _phase_rank(phase: str) -> int:
    return {"de": 2, "pools": 1}.get(phase, 0)


def _status_key(status: FencerStatus) -> tuple:
    return (status.name.lower(), status.event_id)


def _merge_status(existing: Optional[FencerStatus], candidate: FencerStatus) -> FencerStatus:
    if existing is None:
        return candidate

    existing_rank = (_phase_rank(existing.phase), _activity_rank(existing.activity))
    candidate_rank = (_phase_rank(candidate.phase), _activity_rank(candidate.activity))

    if candidate.error and not existing.error:
        return existing

    if candidate_rank > existing_rank:
        return candidate

    return existing


def _round_index(round_label: Optional[str]) -> int:
    if not round_label:
        return -1
    try:
        return _ROUND_ORDER.index(round_label)
    except ValueError:
        return -1


def _choose_latest_match(matches: Iterable[dict]) -> Optional[dict]:
    latest = None
    latest_idx = -1
    for match in matches:
        idx = _round_index(match.get("round"))
        if idx > latest_idx:
            latest = match
            latest_idx = idx
    return latest


def _pool_statuses(bundle: dict, club_filter: str, event) -> list[FencerStatus]:
    statuses = []
    results = bundle.get("results", {})
    result_map = {
        (fencer.get("name") or "").lower(): fencer
        for fencer in results.get("fencers", [])
    }

    for pool in bundle.get("pools", []):
        pool_number = pool.get("pool_number")
        strip = pool.get("strip")

        for fencer in pool.get("fencers", []):
            if not match_club({"club": fencer.get("club")}, club_filter):
                continue

            name = fencer.get("name") or ""
            result = result_map.get(name.lower(), {})
            status = result.get("status") or "unknown"

            activity = "waiting"
            result_text = None
            if status == "eliminated":
                activity = "finished"
                result_text = "Eliminated"
            elif status == "advanced":
                activity = "waiting"
                result_text = "Advanced to DE"
            else:
                activity = "active" if strip else "waiting"

            statuses.append(FencerStatus(
                name=name,
                event_id=event.event_id,
                event_name=event.event_name,
                weapon=event.weapon,
                pool_number=pool_number,
                strip=strip,
                activity=activity,
                phase="pools",
                result=result_text,
                last_updated=datetime.now(UTC).isoformat(),
            ))

    return statuses


def _de_statuses(matches: list[dict], club_filter: str, event) -> list[FencerStatus]:
    statuses = []
    fencer_matches: dict[str, list[dict]] = {}

    for match in matches:
        for side in ("a", "b"):
            name_key = f"name_{side}"
            club_key = f"club_{side}"
            fencer_name = match.get(name_key)
            if not fencer_name:
                continue
            if not match_club({"club": match.get(club_key)}, club_filter):
                continue
            fencer_matches.setdefault(fencer_name, []).append(match)

    for fencer_name, fencer_matches_list in fencer_matches.items():
        latest = _choose_latest_match(fencer_matches_list)
        if not latest:
            continue

        round_label = latest.get("round")
        status = latest.get("status") or "pending"
        winner = latest.get("winner")
        is_a = fencer_name == latest.get("name_a")

        activity = "waiting"
        result_text = None

        if status == "in_progress":
            activity = "active"
        elif status == "pending":
            activity = "waiting"
        elif status == "complete":
            is_winner = (winner == "A" and is_a) or (winner == "B" and not is_a)
            if round_label == "F":
                activity = "finished"
                result_text = "Gold Medal" if is_winner else "Silver Medal"
            elif round_label == "SF" and not is_winner:
                activity = "finished"
                result_text = "Bronze Medal"
            elif is_winner:
                activity = "waiting"
                result_text = f"Advanced to {_NEXT_ROUND_LABELS.get(round_label, 'next round')}"
            else:
                activity = "finished"
                result_text = f"Eliminated (Table of {round_label})" if round_label else "Eliminated"

        statuses.append(FencerStatus(
            name=fencer_name,
            event_id=event.event_id,
            event_name=event.event_name,
            weapon=event.weapon,
            de_round=round_label,
            activity=activity,
            phase="de",
            result=result_text,
            last_updated=datetime.now(UTC).isoformat(),
        ))

    return statuses


def get_tournament_fencer_status(
    tournament_id: int,
    club_filter: str,
    cached_events: list,
    *,
    force_refresh: bool = False,
) -> dict[str, list[FencerStatus]]:
    """
    Aggregate fencer status across all events in a tournament.

    Returns:
        {
            "active": [FencerStatus, ...],
            "waiting": [FencerStatus, ...],
            "finished": [FencerStatus, ...],
        }
    """
    grouped = {"active": [], "waiting": [], "finished": []}
    if not club_filter:
        return grouped

    statuses: dict[tuple, FencerStatus] = {}

    for event in cached_events:
        if event.pool_round_id:
            try:
                bundle = fetch_pools_bundle(
                    event.event_id,
                    event.pool_round_id,
                    force_refresh=force_refresh,
                )
                for status in _pool_statuses(bundle, club_filter, event):
                    key = _status_key(status)
                    statuses[key] = _merge_status(statuses.get(key), status)
            except (FTLHTTPError, FTLParseError, ValueError) as exc:
                logger.warning("Pools fetch failed for event %s: %s", event.event_id, exc)
                error_status = FencerStatus(
                    name=f"{club_filter} fencers",
                    event_id=event.event_id,
                    event_name=event.event_name,
                    weapon=event.weapon,
                    activity="waiting",
                    phase="pools",
                    error="Unable to fetch pool data",
                    last_updated=datetime.now(UTC).isoformat(),
                )
                key = _status_key(error_status)
                statuses[key] = _merge_status(statuses.get(key), error_status)

        if event.de_round_id:
            try:
                html = fetch_tableau_raw(
                    event.event_id,
                    event.de_round_id,
                    force_refresh=force_refresh,
                )
                tableau = parse_de_tableau(html, event_id=event.event_id, round_id=event.de_round_id)
                for status in _de_statuses(tableau.get("matches", []), club_filter, event):
                    key = _status_key(status)
                    statuses[key] = _merge_status(statuses.get(key), status)
            except (FTLHTTPError, FTLParseError, ValueError) as exc:
                logger.warning("DE fetch failed for event %s: %s", event.event_id, exc)
                error_status = FencerStatus(
                    name=f"{club_filter} fencers",
                    event_id=event.event_id,
                    event_name=event.event_name,
                    weapon=event.weapon,
                    activity="waiting",
                    phase="de",
                    error="Unable to fetch DE data",
                    last_updated=datetime.now(UTC).isoformat(),
                )
                key = _status_key(error_status)
                statuses[key] = _merge_status(statuses.get(key), error_status)

    for status in statuses.values():
        if status.activity not in grouped:
            grouped["waiting"].append(status)
        else:
            grouped[status.activity].append(status)

    for group in grouped.values():
        group.sort(key=lambda item: (item.event_name.lower(), item.name.lower()))

    return grouped
