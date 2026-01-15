"""FastAPI application for FTL data service."""
import os
import re
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, dependencies
from app.database import get_db
from app.ftl.client import (
    fetch_pools_bundle,
    fetch_tableau_raw,
    FTLHTTPError,
    FTLParseError,
)
from app.ftl.parsers import parse_de_tableau
from app.models import User


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


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "FTL Data Service"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Dashboard page for authenticated users."""
    return dependencies.templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user},
    )


# Regex for 32-char hex IDs
HEX_ID_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")


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


@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render fencer search form."""
    return dependencies.templates.TemplateResponse(
        request,
        "search.html",
        {"user": user, "values": {}},
    )


@app.get("/pools", response_class=HTMLResponse)
def pools_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render pool overview form."""
    return dependencies.templates.TemplateResponse(
        request,
        "pools.html",
        {"user": user, "values": {}},
    )


@app.get("/advancement", response_class=HTMLResponse)
def advancement_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render advancement status form."""
    return dependencies.templates.TemplateResponse(
        request,
        "advancement.html",
        {"user": user, "values": {}},
    )


@app.get("/de", response_class=HTMLResponse)
def de_page(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
):
    """Render DE tableau form."""
    return dependencies.templates.TemplateResponse(
        request,
        "de_tableau.html",
        {"user": user, "values": {}},
    )


@app.post("/search", response_class=HTMLResponse)
async def search_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle fencer search form submission."""
    form = await request.form()
    event_id = (form.get("event_id") or "").strip()
    pool_round_id = (form.get("pool_round_id") or "").strip()
    name = (form.get("name") or "").strip()

    values = {"event_id": event_id, "pool_round_id": pool_round_id, "name": name}

    # Validate inputs
    if not event_id or not pool_round_id or not name:
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": "All fields are required.", "values": values},
        )

    if not HEX_ID_PATTERN.match(event_id):
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": "Event ID must be a 32-character hex string.", "values": values},
        )

    if not HEX_ID_PATTERN.match(pool_round_id):
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": "Pool Round ID must be a 32-character hex string.", "values": values},
        )

    # Perform search
    try:
        results = _do_fencer_search(event_id, pool_round_id, name, force_refresh=False)
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "values": values, "results": results},
        )
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            error = "The search timed out. Please try again."
        else:
            error = "Unable to reach the tournament server. Please try again later."
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": error, "values": values},
        )
    except FTLParseError:
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": "Error parsing tournament data. The event may not exist.", "values": values},
        )
    except ValueError as e:
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": str(e), "values": values},
        )
    except Exception:
        return dependencies.templates.TemplateResponse(
            request,
            "search.html",
            {"user": user, "error": "An unexpected error occurred. Please try again.", "values": values},
        )


@app.post("/pools", response_class=HTMLResponse)
async def pools_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle pool overview form submission."""
    form = await request.form()
    event_id = (form.get("event_id") or "").strip()
    pool_round_id = (form.get("pool_round_id") or "").strip()

    values = {"event_id": event_id, "pool_round_id": pool_round_id}

    if not event_id or not pool_round_id:
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": "Both fields are required.", "values": values},
        )

    if not HEX_ID_PATTERN.match(event_id):
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": "Event ID must be a 32-character hex string.", "values": values},
        )

    if not HEX_ID_PATTERN.match(pool_round_id):
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": "Pool Round ID must be a 32-character hex string.", "values": values},
        )

    try:
        results = _do_pools_overview(event_id, pool_round_id, force_refresh=False)
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {
                "user": user,
                "values": values,
                "event_id": results["event_id"],
                "pool_round_id": results["pool_round_id"],
                "pools": results["pools"],
            },
        )
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            error = "The request timed out. Please try again."
        else:
            error = "Unable to reach the tournament server. Please try again later."
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": error, "values": values},
        )
    except FTLParseError:
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": "Error parsing tournament data. The event may not exist.", "values": values},
        )
    except ValueError as e:
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": str(e), "values": values},
        )
    except Exception:
        return dependencies.templates.TemplateResponse(
            request,
            "pools.html",
            {"user": user, "error": "An unexpected error occurred. Please try again.", "values": values},
        )


@app.post("/advancement", response_class=HTMLResponse)
async def advancement_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle advancement status form submission."""
    form = await request.form()
    event_id = (form.get("event_id") or "").strip()
    pool_round_id = (form.get("pool_round_id") or "").strip()

    values = {"event_id": event_id, "pool_round_id": pool_round_id}

    if not event_id or not pool_round_id:
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": "Both fields are required.", "values": values},
        )

    if not HEX_ID_PATTERN.match(event_id):
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": "Event ID must be a 32-character hex string.", "values": values},
        )

    if not HEX_ID_PATTERN.match(pool_round_id):
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": "Pool Round ID must be a 32-character hex string.", "values": values},
        )

    try:
        results = _do_advancement_status(event_id, pool_round_id, force_refresh=False)
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {
                "user": user,
                "values": values,
                "event_id": results["event_id"],
                "pool_round_id": results["pool_round_id"],
                "groups": results["groups"],
                "counts": results["counts"],
            },
        )
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            error = "The request timed out. Please try again."
        else:
            error = "Unable to reach the tournament server. Please try again later."
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": error, "values": values},
        )
    except FTLParseError:
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": "Error parsing tournament data. The event may not exist.", "values": values},
        )
    except ValueError as e:
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": str(e), "values": values},
        )
    except Exception:
        return dependencies.templates.TemplateResponse(
            request,
            "advancement.html",
            {"user": user, "error": "An unexpected error occurred. Please try again.", "values": values},
        )


@app.post("/de", response_class=HTMLResponse)
async def de_submit(
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Handle DE tableau form submission."""
    form = await request.form()
    event_id = (form.get("event_id") or "").strip()
    round_id = (form.get("round_id") or "").strip()

    values = {"event_id": event_id, "round_id": round_id}

    if not event_id or not round_id:
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": "Both fields are required.", "values": values},
        )

    if not HEX_ID_PATTERN.match(event_id):
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": "Event ID must be a 32-character hex string.", "values": values},
        )

    if not HEX_ID_PATTERN.match(round_id):
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": "DE Round ID must be a 32-character hex string.", "values": values},
        )

    try:
        results = _do_de_tableau(event_id, round_id, force_refresh=False)
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {
                "user": user,
                "values": values,
                "event_id": results["event_id"],
                "round_id": results["round_id"],
                "groups": results["groups"],
            },
        )
    except FTLHTTPError as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "Timeout" in error_msg:
            error = "The request timed out. Please try again."
        else:
            error = "Unable to reach the tournament server. Please try again later."
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": error, "values": values},
        )
    except FTLParseError:
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": "Error parsing tableau data. The event may not exist.", "values": values},
        )
    except ValueError as e:
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": str(e), "values": values},
        )
    except Exception:
        return dependencies.templates.TemplateResponse(
            request,
            "de_tableau.html",
            {"user": user, "error": "An unexpected error occurred. Please try again.", "values": values},
        )


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
