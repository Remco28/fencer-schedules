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
