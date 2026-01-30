"""Tournament fencer status orchestration."""
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, Optional, Iterable, Union

from app.ftl.client import (
    fetch_competitors_json,
    fetch_pools_bundle,
    fetch_tableau_raw,
    fetch_event_results_json,
    FTLHTTPError,
    FTLParseError,
)
from app.ftl.parsers.de_tableau import parse_de_tableau
from app.services.club_matcher import match_club

logger = logging.getLogger(__name__)

# Cache TTL constants
TTL_SHORT = 180  # 3 minutes for active events
TTL_LONG = 86400  # 24 hours for completed events


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
    source: str = "club"
    fencer_db_id: Optional[int] = None


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
    # "complete" is final results, highest priority
    return {"complete": 3, "de": 2, "pools": 1}.get(phase, 0)


def _status_key(status: FencerStatus) -> tuple:
    return (status.name.lower(), status.event_id)


def _merge_status(existing: Optional[FencerStatus], candidate: FencerStatus) -> FencerStatus:
    if existing is None:
        return candidate

    existing_rank = (_phase_rank(existing.phase), _activity_rank(existing.activity))
    candidate_rank = (_phase_rank(candidate.phase), _activity_rank(candidate.activity))

    if existing.source == "club" and candidate.source == "manual":
        return existing
    if existing.source == "manual" and candidate.source == "club":
        return candidate

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


def _is_event_completed_from_tableau(matches: list[dict]) -> bool:
    """Check if an event is completed by examining DE tableau matches.

    An event is complete when the Final match (round="F") has status="complete".
    """
    for match in matches:
        if match.get("round") == "F" and match.get("status") == "complete":
            return True
    return False


def _mark_event_completed(event: Any, db: Any) -> None:
    """Mark an event as completed in the database.

    Args:
        event: CachedEvent model instance
        db: SQLAlchemy session (optional)
    """
    if db is None:
        return
    if getattr(event, "is_completed", False):
        return  # Already marked

    try:
        event.is_completed = True
        event.completed_at = datetime.now(UTC)
        db.add(event)
        # Don't commit here - let the caller manage the transaction
        logger.info("Marked event %s (%s) as completed", event.event_id, event.event_name)
    except Exception as exc:
        logger.warning("Failed to mark event %s as completed: %s", event.event_id, exc)


def _choose_latest_match(matches: Iterable[dict]) -> Optional[dict]:
    latest = None
    latest_idx = -1
    for match in matches:
        idx = _round_index(match.get("round"))
        if idx > latest_idx:
            latest = match
            latest_idx = idx
    return latest


def _pool_statuses(
    bundle: dict,
    club_filter: Union[str, list[str]],
    event,
    manual_fencers: dict[str, int],
) -> list[FencerStatus]:
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
            name = fencer.get("name") or ""
            name_lower = name.lower()
            is_manual = name_lower in manual_fencers
            is_club = match_club({"club": fencer.get("club")}, club_filter)
            if not is_manual and not is_club:
                continue

            result = result_map.get(name_lower, {})
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
                source="club" if is_club else "manual",
                fencer_db_id=manual_fencers.get(name_lower),
            ))

    return statuses


def _results_statuses(
    results: list[dict],
    club_filter: Union[str, list[str]],
    event,
    manual_fencers: dict[str, int],
) -> list[FencerStatus]:
    """
    Convert event results JSON to FencerStatus objects.

    This is used for completed events where the DE tableau is no longer available
    via simple HTTP fetch (FTL loads tableau data via JavaScript).

    Args:
        results: List of result dicts from /events/results/data endpoint
        club_filter: Club name to filter by
        event: Event object with event_id, event_name, weapon

    Returns:
        List of FencerStatus objects for fencers matching the club filter
    """
    statuses = []

    for result in results:
        # Check if fencer matches club filter
        # Results have: clubs, club1, club2 fields
        fencer_data = {
            "club": result.get("clubs") or result.get("club1") or ""
        }
        name = result.get("name", "")
        name_lower = name.lower()
        is_manual = name_lower in manual_fencers
        is_club = match_club(fencer_data, club_filter)
        if not is_manual and not is_club:
            continue

        place = result.get("place", "")

        # Determine result text based on placement
        result_text = f"Place: {place}" if place else "Complete"

        statuses.append(FencerStatus(
            name=name,
            event_id=event.event_id,
            event_name=event.event_name,
            weapon=event.weapon,
            activity="finished",
            phase="complete",
            result=result_text,
            last_updated=datetime.now(UTC).isoformat(),
            source="club" if is_club else "manual",
            fencer_db_id=manual_fencers.get(name_lower),
        ))

    return statuses


def _de_statuses(
    matches: list[dict],
    club_filter: Union[str, list[str]],
    event,
    manual_fencers: dict[str, int],
) -> list[FencerStatus]:
    statuses = []
    fencer_matches: dict[str, list[dict]] = {}

    for match in matches:
        for side in ("a", "b"):
            name_key = f"name_{side}"
            club_key = f"club_{side}"
            fencer_name = match.get(name_key)
            if not fencer_name:
                continue
            name_lower = fencer_name.lower()
            is_manual = name_lower in manual_fencers
            is_club = match_club({"club": match.get(club_key)}, club_filter)
            if not is_manual and not is_club:
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

        name_lower = fencer_name.lower()
        is_club = match_club({"club": latest.get("club_a") if is_a else latest.get("club_b")}, club_filter)
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
            source="club" if is_club else "manual",
            fencer_db_id=manual_fencers.get(name_lower),
        ))

    return statuses


def get_tournament_fencer_status(
    tournament_id: int,
    club_filter: Union[str, list[str]],
    cached_events: list,
    tracked_fencers: Optional[list] = None,
    *,
    force_refresh: bool = False,
    db: Any = None,
) -> dict[str, list[FencerStatus]]:
    """
    Aggregate fencer status across all events in a tournament.

    Uses smart caching: completed events use 24-hour TTL, active events use 3-minute TTL.

    Args:
        tournament_id: Tournament database ID
        club_filter: Club name (or list of names) to filter fencers by
        cached_events: List of CachedEvent model instances
        tracked_fencers: List of TrackedFencer model instances (optional)
        force_refresh: Bypass cache and force fresh fetch
        db: SQLAlchemy session for marking events as completed (optional)

    Returns:
        {
            "active": [FencerStatus, ...],
            "waiting": [FencerStatus, ...],
            "finished": [FencerStatus, ...],
        }
    """
    grouped = {"active": [], "waiting": [], "finished": []}
    manual_fencers = {
        fencer.fencer_name.lower(): fencer.id
        for fencer in (tracked_fencers or [])
        if fencer.source == "manual"
    }
    if not club_filter and not manual_fencers:
        return grouped

    statuses: dict[tuple, FencerStatus] = {}

    for event in cached_events:
        # Smart TTL: use long cache for completed events
        event_completed = getattr(event, "is_completed", False)
        ttl = TTL_LONG if event_completed else TTL_SHORT

        if event.pool_round_id:
            try:
                bundle = fetch_pools_bundle(
                    event.event_id,
                    event.pool_round_id,
                    force_refresh=force_refresh,
                    ttl=ttl,
                )
                for status in _pool_statuses(bundle, club_filter, event, manual_fencers):
                    key = _status_key(status)
                    statuses[key] = _merge_status(statuses.get(key), status)
            except (FTLHTTPError, FTLParseError, ValueError) as exc:
                logger.warning("Pools fetch failed for event %s: %s", event.event_id, exc)
                if club_filter or manual_fencers:
                    error_status = FencerStatus(
                        name=f"{club_filter or 'Tracked'} fencers",
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
                    ttl=ttl,
                )
                tableau = parse_de_tableau(html, event_id=event.event_id, round_id=event.de_round_id)
                matches = tableau.get("matches", [])
                for status in _de_statuses(matches, club_filter, event, manual_fencers):
                    key = _status_key(status)
                    statuses[key] = _merge_status(statuses.get(key), status)

                # Detect completion from DE tableau (Final match complete)
                if not event_completed and _is_event_completed_from_tableau(matches):
                    _mark_event_completed(event, db)

            except (FTLHTTPError, FTLParseError, ValueError) as exc:
                # DE tableau page uses JavaScript rendering, so parsing fails.
                # Fall back to event results endpoint which works for completed events.
                logger.info("DE tableau parse failed for event %s, trying results endpoint: %s", event.event_id, exc)
                try:
                    results = fetch_event_results_json(
                        event.event_id,
                        force_refresh=force_refresh,
                        ttl=TTL_LONG,  # Results only exist for completed events
                    )
                    for status in _results_statuses(results, club_filter, event, manual_fencers):
                        key = _status_key(status)
                        statuses[key] = _merge_status(statuses.get(key), status)

                    # If we got results, the event is definitely completed
                    if results and not event_completed:
                        _mark_event_completed(event, db)

                except (FTLHTTPError, FTLParseError, ValueError) as results_exc:
                    logger.warning("Results fetch also failed for event %s: %s", event.event_id, results_exc)
                    if club_filter or manual_fencers:
                        error_status = FencerStatus(
                            name=f"{club_filter or 'Tracked'} fencers",
                            event_id=event.event_id,
                            event_name=event.event_name,
                            weapon=event.weapon,
                            activity="waiting",
                            phase="de",
                            error="Unable to fetch DE or results data",
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


def _generate_name_variants(query: str) -> list[str]:
    """
    Generate name search variants to handle "John Smith" vs "SMITH John" formats.

    FTL stores names as "LASTNAME Firstname" but users often search "Firstname Lastname".
    Returns list of search patterns to check.
    """
    query = query.strip()
    if not query:
        return []

    variants = [query.lower()]

    # If query has spaces, try permutations
    parts = query.split()
    if len(parts) >= 2:
        # "John Smith" → also try "Smith John", "SMITH John", "Smith, John"
        reversed_parts = parts[::-1]
        variants.append(" ".join(reversed_parts).lower())
        # Also try with comma: "Smith, John"
        variants.append(f"{reversed_parts[0]}, {' '.join(reversed_parts[1:])}".lower())
        # Try individual parts for partial matching
        for part in parts:
            if len(part) >= 2:
                variants.append(part.lower())

    return list(dict.fromkeys(variants))  # Remove duplicates, preserve order


def _matches_name_query(name: str, query_variants: list[str]) -> bool:
    """Check if a fencer name matches any of the query variants."""
    name_lower = name.lower()
    for variant in query_variants:
        if variant in name_lower:
            return True
    return False


def search_tournament_fencers(
    tournament_id: int,
    cached_events: list,
    query: str,
    force_refresh: bool = False,
) -> list[dict]:
    """
    Search for fencers across all events in a tournament.

    Handles name format differences (e.g., "John Smith" finds "SMITH John").

    Returns:
        List of fencer dicts with keys: name, event_id, event_name, club, status
    """
    if not query or len(query.strip()) < 2:
        return []

    query_variants = _generate_name_variants(query)
    results = []
    seen = set()

    for event in cached_events:
        try:
            competitors = fetch_competitors_json(
                event.event_id,
                force_refresh=force_refresh,
            )
            for comp in competitors:
                name = comp.get("name", "")
                if _matches_name_query(name, query_variants):
                    key = (name, event.event_id)
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "name": name,
                            "event_id": event.event_id,
                            "event_name": event.event_name,
                            "club": comp.get("club1") or comp.get("clubs") or "",
                            "status": "registered",
                        })
        except Exception:
            if event.pool_round_id:
                try:
                    bundle = fetch_pools_bundle(
                        event.event_id,
                        event.pool_round_id,
                        force_refresh=force_refresh,
                    )
                    for pool in bundle.get("pools", []):
                        for fencer in pool.get("fencers", []):
                            name = fencer.get("name", "")
                            if _matches_name_query(name, query_variants):
                                key = (name, event.event_id)
                                if key not in seen:
                                    seen.add(key)
                                    results.append({
                                        "name": name,
                                        "event_id": event.event_id,
                                        "event_name": event.event_name,
                                        "club": fencer.get("club") or "",
                                        "status": "in_pools",
                                    })
                except Exception:
                    pass

    results.sort(key=lambda item: item["name"].lower())
    return results
