"""FastAPI application for FTL data service."""
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.api import auth, dependencies
from app import crud
from app.services.club_matcher import match_club
from app.services.cleanup_service import cleanup_expired_tournaments, touch_tournament_access
from app.database import get_db
from app.ftl.client import (
    fetch_pools_bundle,
    fetch_tableau_raw,
    fetch_tournament_schedule,
    fetch_event_page,
    fetch_competitors_json,
    FTLHTTPError,
    FTLParseError,
)
from app.ftl.parsers import parse_de_tableau, parse_event_rounds, parse_tournament_schedule
from app.models import CachedEvent, TrackedFencer, TrackedTournament, User
from app.services.tournament_service import get_tournament_fencer_status


# Configuration from environment variables with defaults
TIMEOUT = int(os.getenv("FTL_TIMEOUT", "10"))
MAX_WORKERS = int(os.getenv("FTL_MAX_WORKERS", "8"))
CACHE_TTL = int(os.getenv("FTL_CACHE_TTL", "180"))


app = FastAPI(
    title="Fencer Schedules",
    description="Live tournament tracking and personalized schedules",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include auth router
app.include_router(auth.router)

logger = logging.getLogger(__name__)


@app.on_event("startup")
def on_startup():
    """Initialize database tables on startup."""
    from app.database import init_db
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint for orchestration."""
    return {"status": "ok"}


@app.get("/")
def root(
    request: Request,
    user: User | None = Depends(dependencies.get_optional_user),
):
    """Redirect to dashboard if logged in, otherwise login page."""
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Dashboard page for authenticated users."""
    now = datetime.now(UTC)
    ttl_hours = int(os.getenv("TOURNAMENT_TTL_HOURS", "48"))
    cleanup_expired_tournaments(db, now, ttl_hours)
    db.commit()

    tournaments = (
        db.query(TrackedTournament)
        .filter(TrackedTournament.user_id == user.id)
        .options(selectinload(TrackedTournament.events))
        .order_by(TrackedTournament.created_at.desc())
        .all()
    )

    for tournament in tournaments:
        touch_tournament_access(db, tournament, now)
    db.commit()

    return dependencies.templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "tournaments": tournaments},
    )


@app.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render the user profile page."""
    return dependencies.templates.TemplateResponse(
        request,
        "profile.html",
        {"user": user},
    )


@app.post("/profile", response_class=HTMLResponse)
async def profile_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle user profile updates."""
    form = await request.form()
    username = (form.get("username") or "").strip()
    email = (form.get("email") or "").strip()
    club_raw = (form.get("club") or "").strip()
    club = club_raw or None

    values = {"username": username, "email": email, "club": club_raw}
    errors: Dict[str, str] = {}

    if not username:
        errors["username"] = "Username is required."
    elif len(username) < 3:
        errors["username"] = "Username must be at least 3 characters long."
    elif len(username) > 50:
        errors["username"] = "Username must be 50 characters or fewer."

    if not email:
        errors["email"] = "Email is required."
    elif not EMAIL_PATTERN.match(email):
        errors["email"] = "Email must be a valid address."

    if club_raw and len(club_raw) > 200:
        errors["club"] = "Club must be 200 characters or fewer."

    if username and username != user.username:
        existing = crud.get_user_by_username(db, username)
        if existing and existing.id != user.id:
            errors["username"] = "Username already exists."

    if email and email != user.email:
        existing = crud.get_user_by_email(db, email)
        if existing and existing.id != user.id:
            errors["email"] = "Email already exists."

    if errors:
        return dependencies.templates.TemplateResponse(
            request,
            "profile.html",
            {"user": user, "values": values, "errors": errors},
        )

    try:
        updated_user = crud.update_user_profile(db, user.id, username, email, club)
        db.commit()
        db.refresh(updated_user)
    except Exception:
        db.rollback()
        return dependencies.templates.TemplateResponse(
            request,
            "profile.html",
            {
                "user": user,
                "values": values,
                "errors": {"form": "Unable to update profile. Please try again."},
            },
        )

    return dependencies.templates.TemplateResponse(
        request,
        "profile.html",
        {"user": updated_user, "success": True},
    )


# Regex for 32-char hex IDs
HEX_ID_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOURNAMENT_URL_PATTERN = re.compile(
    r"fencingtimelive\.com/tournaments/(?:eventSchedule|scores)/([A-Fa-f0-9]{32})"
)


def extract_tournament_id(url: str) -> str | None:
    """Extract tournament ID from FTL URL."""
    match = TOURNAMENT_URL_PATTERN.search(url)
    return match.group(1) if match else None


def _build_tournament_events(
    db: Session,
    tracked: TrackedTournament,
    *,
    force_refresh: bool = False,
) -> int:
    """Fetch and cache tournament events for a tracked tournament."""
    schedule_html = fetch_tournament_schedule(tracked.tournament_id, timeout=TIMEOUT)
    schedule = parse_tournament_schedule(schedule_html)

    tournament_name = schedule.get("tournament_name")
    if tournament_name:
        tracked.tournament_name = tournament_name

    events = schedule.get("events", [])
    if tracked.weapon_filter:
        events = [event for event in events if event.get("weapon") == tracked.weapon_filter]

    created = 0
    for event in events:
        event_id = event.get("event_id")
        if not event_id:
            continue

        try:
            event_html = fetch_event_page(event_id, timeout=TIMEOUT)
            rounds = parse_event_rounds(event_html)
            pool_round_id = rounds.get("pool_round_id")
            de_round_id = rounds.get("de_round_id")
        except Exception as exc:
            logger.warning("Failed to discover rounds for event %s: %s", event_id, exc)
            continue

        fencer_count = 0
        if tracked.club_filter:
            try:
                competitors = fetch_competitors_json(
                    event_id,
                    timeout=TIMEOUT,
                    force_refresh=force_refresh,
                )
                fencer_count = sum(1 for fencer in competitors if match_club(fencer, tracked.club_filter))
            except Exception as exc:
                logger.warning("Failed to fetch competitors for event %s: %s", event_id, exc)
                fencer_count = 0

        cached_event = CachedEvent(
            tracked_tournament_id=tracked.id,
            event_id=event_id,
            event_name=event.get("name") or "Unknown Event",
            weapon=event.get("weapon"),
            start_date=event.get("date"),
            start_time=event.get("start_time"),
            pool_round_id=pool_round_id,
            de_round_id=de_round_id,
            fencer_count=fencer_count,
        )
        db.add(cached_event)
        created += 1

    return created


@app.get("/tournament/new", response_class=HTMLResponse)
def tournament_new_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render tournament tracking form."""
    return dependencies.templates.TemplateResponse(
        request,
        "tournament_new.html",
        {"user": user, "values": {}},
    )


@app.post("/tournament/new", response_class=HTMLResponse)
async def tournament_new_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle tournament tracking setup."""
    form = await request.form()
    url = (form.get("url") or "").strip()
    club_raw = (form.get("club") or "").strip()
    club_filter = club_raw or None
    weapon_filter = (form.get("weapon") or "").strip() or None

    values = {"url": url, "club": club_raw, "weapon": weapon_filter or ""}

    tournament_id = extract_tournament_id(url)
    if not tournament_id:
        return dependencies.templates.TemplateResponse(
            request,
            "tournament_new.html",
            {"user": user, "error": "Enter a valid FencingTimeLive tournament URL.", "values": values},
        )

    if weapon_filter not in {None, "Epee", "Foil", "Saber"}:
        return dependencies.templates.TemplateResponse(
            request,
            "tournament_new.html",
            {"user": user, "error": "Select a valid weapon filter.", "values": values},
        )

    tracked = TrackedTournament(
        user_id=user.id,
        tournament_id=tournament_id,
        tournament_name=f"Tournament {tournament_id}",
        tournament_url=url,
        club_filter=club_filter,
        weapon_filter=weapon_filter,
    )
    db.add(tracked)
    db.flush()

    try:
        _build_tournament_events(db, tracked)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to fetch tournament schedule %s: %s", tournament_id, exc)
        return dependencies.templates.TemplateResponse(
            request,
            "tournament_new.html",
            {"user": user, "error": "Unable to fetch tournament schedule.", "values": values},
        )

    return RedirectResponse(
        url=f"/tournament/{tracked.id}",
        status_code=303,
    )


@app.get("/tournament/{tournament_id}", response_class=HTMLResponse)
def tournament_detail(
    tournament_id: int,
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Show tracked tournament details."""
    tournament = (
        db.query(TrackedTournament)
        .options(selectinload(TrackedTournament.events))
        .filter(TrackedTournament.id == tournament_id)
        .first()
    )
    if not tournament or tournament.user_id != user.id:
        raise HTTPException(status_code=404, detail="Tournament not found")

    now = datetime.now(UTC)
    touch_tournament_access(db, tournament, now)
    db.commit()

    return dependencies.templates.TemplateResponse(
        request,
        "tournament_detail.html",
        {"user": user, "tournament": tournament},
    )


@app.get("/tournament/{tournament_id}/dashboard", response_class=HTMLResponse)
def tournament_dashboard(
    tournament_id: int,
    request: Request,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(dependencies.get_current_user),
):
    """Consolidated dashboard showing all club fencers across events."""
    tournament = (
        db.query(TrackedTournament)
        .options(
            selectinload(TrackedTournament.events),
            selectinload(TrackedTournament.tracked_fencers),
        )
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    now = datetime.now(UTC)
    touch_tournament_access(db, tournament, now)
    db.commit()

    try:
        grouped_fencers = get_tournament_fencer_status(
            tournament_id=tournament.id,
            club_filter=tournament.club_filter or "",
            cached_events=tournament.events,
            tracked_fencers=tournament.tracked_fencers,
            force_refresh=force_refresh,
            db=db,  # Pass db for smart caching (marks completed events)
        )
        # Commit any event completion flags that were set
        db.commit()
    except Exception as exc:
        logger.warning("Failed to fetch tournament dashboard %s: %s", tournament.id, exc)
        return dependencies.templates.TemplateResponse(
            request,
            "tournament_dashboard.html",
            {
                "user": user,
                "tournament": tournament,
                "error": f"Failed to fetch fencer data: {exc}",
                "grouped_fencers": {"active": [], "waiting": [], "finished": []},
            },
        )

    return dependencies.templates.TemplateResponse(
        request,
        "tournament_dashboard.html",
        {
            "user": user,
            "tournament": tournament,
            "grouped_fencers": grouped_fencers,
            "last_updated": now.strftime("%I:%M %p"),
        },
    )


@app.get("/tournament/{tournament_id}/search", response_class=HTMLResponse)
def tournament_search_page(
    tournament_id: int,
    request: Request,
    q: str = "",
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Search for fencers within a tournament."""
    tournament = (
        db.query(TrackedTournament)
        .options(selectinload(TrackedTournament.events))
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    now = datetime.now(UTC)
    touch_tournament_access(db, tournament, now)
    db.commit()

    results = []
    error = None

    if q and len(q) >= 2:
        try:
            from app.services.tournament_service import search_tournament_fencers

            results = search_tournament_fencers(
                tournament_id=tournament.id,
                cached_events=tournament.events,
                query=q,
            )
            tracked_names = {
                fencer.fencer_name.lower()
                for fencer in crud.get_tracked_fencers(db, tournament.id)
            }
            for result in results:
                result["is_tracked"] = result["name"].lower() in tracked_names
        except Exception as exc:
            error = f"Search failed: {exc}"

    return dependencies.templates.TemplateResponse(
        request,
        "tournament_search.html",
        {
            "user": user,
            "tournament": tournament,
            "query": q,
            "results": results,
            "error": error,
        },
    )


@app.post("/tournament/{tournament_id}/track")
async def add_tracked_fencer(
    tournament_id: int,
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Add a fencer to tracking list."""
    tournament = (
        db.query(TrackedTournament)
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    form = await request.form()
    fencer_name = (form.get("fencer_name") or "").strip()

    if not fencer_name:
        return RedirectResponse(
            url=f"/tournament/{tournament_id}/search",
            status_code=303,
        )

    if not crud.is_fencer_tracked(db, tournament.id, fencer_name):
        crud.add_tracked_fencer(db, tournament.id, fencer_name, source="manual")
        db.commit()

    redirect_url = form.get("redirect_url") or f"/tournament/{tournament_id}/dashboard"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/tournament/{tournament_id}/untrack/{fencer_id}")
def remove_tracked_fencer(
    tournament_id: int,
    fencer_id: int,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Remove a fencer from tracking list."""
    tournament = (
        db.query(TrackedTournament)
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    crud.remove_tracked_fencer(db, fencer_id, tournament.id)
    db.commit()

    return RedirectResponse(
        url=f"/tournament/{tournament_id}/dashboard",
        status_code=303,
    )


@app.post("/tournament/{tournament_id}/restore")
def restore_tournament(
    tournament_id: int,
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Restore an archived tournament."""
    tournament = (
        db.query(TrackedTournament)
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.archived_at:
        return RedirectResponse(url=f"/tournament/{tournament_id}/dashboard", status_code=303)

    db.query(CachedEvent).filter(
        CachedEvent.tracked_tournament_id == tournament.id
    ).delete(synchronize_session=False)
    db.query(TrackedFencer).filter(
        TrackedFencer.tracked_tournament_id == tournament.id
    ).delete(synchronize_session=False)

    try:
        _build_tournament_events(db, tournament, force_refresh=True)
        tournament.archived_at = None
        now = datetime.now(UTC)
        touch_tournament_access(db, tournament, now)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to restore tournament %s: %s", tournament.id, exc)
        return dependencies.templates.TemplateResponse(
            request,
            "tournament_detail.html",
            {
                "user": user,
                "tournament": tournament,
                "error": "Unable to restore tournament.",
            },
        )

    return RedirectResponse(url=f"/tournament/{tournament_id}/dashboard", status_code=303)


@app.post("/tournament/{tournament_id}/delete")
def tournament_delete(
    tournament_id: int,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Delete a tracked tournament."""
    tournament = (
        db.query(TrackedTournament)
        .filter(TrackedTournament.id == tournament_id)
        .first()
    )
    if not tournament or tournament.user_id != user.id:
        raise HTTPException(status_code=404, detail="Tournament not found")

    db.delete(tournament)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


def _do_fencer_search(
    event_id: str,
    pool_round_id: str,
    name: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Internal helper for fencer search logic.

    Fetches pools bundle and searches for fencer by name (case-insensitive substring).
    Returns dict with 'query' and 'matches' keys.
    Raises FTLHTTPError, FTLParseError, or ValueError on failure.
    """
    bundle = fetch_pools_bundle(
        event_id,
        pool_round_id,
        force_refresh=force_refresh,
        timeout=TIMEOUT,
        max_workers=MAX_WORKERS,
    )

    query_lower = name.lower().strip()
    matches = []
    seen = set()

    # Search in pool rosters
    for pool in bundle.get("pools", []):
        pool_number = pool.get("pool_number")
        strip = pool.get("strip")

        for fencer in pool.get("fencers", []):
            fencer_name = fencer.get("name", "")
            if query_lower in fencer_name.lower():
                match_key = (fencer_name.lower(), pool_number)
                if match_key not in seen:
                    seen.add(match_key)
                    matches.append({
                        "name": fencer_name,
                        "pool_number": pool_number,
                        "strip": strip,
                        "club": fencer.get("club"),
                        "seed": fencer.get("seed"),
                        "indicator": fencer.get("indicator"),
                        "status": "unknown",
                        "source": "pool",
                    })

    # Search in pool results
    results = bundle.get("results", {})
    for fencer_result in results.get("fencers", []):
        fencer_name = fencer_result.get("name", "")
        if query_lower in fencer_name.lower():
            match_key = (fencer_name.lower(), None)
            if match_key not in seen:
                seen.add(match_key)
                matches.append({
                    "name": fencer_name,
                    "pool_number": None,
                    "strip": None,
                    "club": fencer_result.get("club_primary"),
                    "place": fencer_result.get("place"),
                    "victories": fencer_result.get("victories"),
                    "matches": fencer_result.get("matches"),
                    "status": fencer_result.get("status"),
                    "source": "results",
                })

    return {"query": name, "matches": matches}


def _do_pools_overview(
    event_id: str,
    pool_round_id: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Internal helper for pool overview data.

    Fetches pools bundle and merges fencer statuses from pool results.
    Returns dict with event_id, pool_round_id, and normalized pools list.
    """
    bundle = fetch_pools_bundle(
        event_id,
        pool_round_id,
        force_refresh=force_refresh,
        timeout=TIMEOUT,
        max_workers=MAX_WORKERS,
    )

    pools = bundle.get("pools", [])
    results = bundle.get("results", {})
    results_fencers = results.get("fencers", [])

    exact_map = {}
    lower_map = {}
    for fencer_result in results_fencers:
        name = fencer_result.get("name")
        if not name:
            continue
        exact_map[name] = fencer_result
        lower_map.setdefault(name.lower(), []).append(fencer_result)

    normalized_pools = []
    for pool in pools:
        normalized_fencers = []
        for fencer in pool.get("fencers", []):
            name = fencer.get("name", "")
            status = "unknown"
            if name in exact_map:
                status = exact_map[name].get("status") or "unknown"
            else:
                candidates = lower_map.get(name.lower(), [])
                if candidates:
                    status = candidates[0].get("status") or "unknown"

            normalized_fencers.append({
                "name": name,
                "club": fencer.get("club"),
                "status": status,
            })

        normalized_pools.append({
            "pool_number": pool.get("pool_number"),
            "strip": pool.get("strip"),
            "fencers": normalized_fencers,
        })

    return {
        "event_id": event_id,
        "pool_round_id": pool_round_id,
        "pools": normalized_pools,
    }


def _do_advancement_status(
    event_id: str,
    pool_round_id: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Internal helper for advancement status data.

    Fetches pools bundle and groups fencers by advancement status.
    Returns dict with grouped fencers and counts.
    """
    bundle = fetch_pools_bundle(
        event_id,
        pool_round_id,
        force_refresh=force_refresh,
        timeout=TIMEOUT,
        max_workers=MAX_WORKERS,
    )

    results = bundle.get("results", {})
    fencers = results.get("fencers", [])

    groups = {"advanced": [], "eliminated": [], "unknown": []}
    for fencer in fencers:
        status = fencer.get("status") or "unknown"
        if status not in groups:
            status = "unknown"
        groups[status].append({
            "name": fencer.get("name", ""),
            "club": fencer.get("club_primary"),
            "place": fencer.get("place"),
            "status": status,
        })

    def sort_key(item: Dict[str, Any]) -> tuple:
        place = item.get("place")
        place_value = None
        if isinstance(place, int):
            place_value = place
        elif isinstance(place, str):
            stripped = place.strip()
            if stripped.isdigit():
                place_value = int(stripped)
        if place_value is None:
            place_value = 10**9
        name = (item.get("name") or "").lower()
        return (place_value == 10**9, place_value, name)

    for status, items in groups.items():
        items.sort(key=sort_key)

    counts = {
        "advanced": len(groups["advanced"]),
        "eliminated": len(groups["eliminated"]),
        "unknown": len(groups["unknown"]),
    }
    counts["total"] = sum(counts.values())

    return {
        "event_id": event_id,
        "pool_round_id": pool_round_id,
        "groups": groups,
        "counts": counts,
    }


def _do_de_tableau(
    event_id: str,
    round_id: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Internal helper for DE tableau data.

    Fetches tableau HTML and parses matches, grouped by round label.
    """
    html = fetch_tableau_raw(
        event_id,
        round_id,
        timeout=TIMEOUT,
        force_refresh=force_refresh,
    )

    tableau = parse_de_tableau(html, event_id=event_id, round_id=round_id)
    matches = tableau.get("matches", [])

    label_map = {
        "64": "Table of 64",
        "32": "Table of 32",
        "16": "Table of 16",
        "8": "Table of 8",
        "QF": "Quarterfinal",
        "SF": "Semifinal",
        "F": "Final",
    }

    grouped: Dict[str, list] = {}
    for match in matches:
        round_key = match.get("round") or "Other"
        label = label_map.get(round_key, round_key if round_key != "Other" else "Other")
        grouped.setdefault(label, []).append(match)

    def match_sort_key(item: Dict[str, Any]) -> tuple:
        path = item.get("path") or ""
        seed_a = item.get("seed_a") or 10**9
        seed_b = item.get("seed_b") or 10**9
        name_a = (item.get("name_a") or "").lower()
        name_b = (item.get("name_b") or "").lower()
        return (path == "", path, seed_a, seed_b, name_a, name_b)

    groups = []
    for label, items in grouped.items():
        items.sort(key=match_sort_key)
        groups.append({"label": label, "matches": items})

    return {
        "event_id": event_id,
        "round_id": round_id,
        "groups": groups,
    }


@app.get("/api/pools/{event_id}/{pool_round_id}")
def get_pools_bundle(
    event_id: str,
    pool_round_id: str,
    force_refresh: bool = Query(False, description="Bypass cache and force fresh fetch"),
):
    """
    Fetch complete pools data bundle for an event/round.

    Returns pool IDs, parsed pool details, and pool results with advancement status.

    Args:
        event_id: FTL event UUID
        pool_round_id: FTL pool round UUID
        force_refresh: If true, bypass cache

    Returns:
        dict with keys: event_id, pool_round_id, pool_ids, pools, results
    """
    try:
        bundle = fetch_pools_bundle(
            event_id,
            pool_round_id,
            force_refresh=force_refresh,
            timeout=TIMEOUT,
            max_workers=MAX_WORKERS,
        )
        return bundle
    except FTLParseError as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")
    except FTLHTTPError as e:
        # Map to 502 for upstream errors, 504 for timeouts
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            raise HTTPException(status_code=504, detail=f"Gateway timeout: {error_msg}")
        else:
            raise HTTPException(status_code=502, detail=f"Upstream error: {error_msg}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/pools/{event_id}/{pool_round_id}/fencer")
def search_fencer(
    event_id: str,
    pool_round_id: str,
    name: str = Query(..., description="Fencer name to search (case-insensitive substring match)"),
    force_refresh: bool = Query(False, description="Bypass cache and force fresh fetch"),
):
    """
    Search for a fencer across pools and results.

    Performs case-insensitive substring match on fencer names.
    Returns matches from both pool rosters and pool results.

    Args:
        event_id: FTL event UUID
        pool_round_id: FTL pool round UUID
        name: Search query (case-insensitive)
        force_refresh: If true, bypass cache

    Returns:
        dict with query and matches array
    """
    try:
        return _do_fencer_search(event_id, pool_round_id, name, force_refresh)
    except FTLParseError as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            raise HTTPException(status_code=504, detail=f"Gateway timeout: {error_msg}")
        else:
            raise HTTPException(status_code=502, detail=f"Upstream error: {error_msg}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/de/{event_id}/{round_id}")
def get_de_tableau(
    event_id: str,
    round_id: str,
    force_refresh: bool = Query(False, description="Bypass cache and force fresh fetch"),
):
    """
    Fetch DE (Direct Elimination) tableau data for an event/round.

    Returns parsed bracket matches with scores, status, and fencer details.

    Args:
        event_id: FTL event UUID
        round_id: FTL DE round UUID
        force_refresh: If true, bypass cache

    Returns:
        dict with keys: event_id, round_id, matches
    """
    try:
        # Fetch tableau HTML
        html = fetch_tableau_raw(
            event_id,
            round_id,
            timeout=TIMEOUT,
            force_refresh=force_refresh,
        )

        # Parse tableau
        tableau = parse_de_tableau(html, event_id=event_id, round_id=round_id)

        return tableau

    except FTLParseError as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            raise HTTPException(status_code=504, detail=f"Gateway timeout: {error_msg}")
        else:
            raise HTTPException(status_code=502, detail=f"Upstream error: {error_msg}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
