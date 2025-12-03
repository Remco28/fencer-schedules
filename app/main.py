"""FastAPI application for FTL data service."""
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import os

from app.ftl.client import (
    fetch_pools_bundle,
    fetch_tableau_raw,
    FTLHTTPError,
    FTLParseError,
)
from app.ftl.parsers import parse_de_tableau


# Configuration from environment variables with defaults
TIMEOUT = int(os.getenv("FTL_TIMEOUT", "10"))
MAX_WORKERS = int(os.getenv("FTL_MAX_WORKERS", "8"))
CACHE_TTL = int(os.getenv("FTL_CACHE_TTL", "180"))


app = FastAPI(
    title="FTL Data Service",
    description="API for fetching and parsing FencingTimeLive tournament data",
    version="1.0.0",
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "FTL Data Service"}


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
        # Fetch pools bundle (reuse to avoid double fetch)
        bundle = fetch_pools_bundle(
            event_id,
            pool_round_id,
            force_refresh=force_refresh,
            timeout=TIMEOUT,
            max_workers=MAX_WORKERS,
        )

        # Normalize search query
        query_lower = name.lower().strip()

        matches = []
        seen = set()  # De-duplicate by (name, pool_number)

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
                            "status": "unknown",  # Pool roster doesn't have advancement status
                            "source": "pool",
                        })

        # Search in pool results
        results = bundle.get("results", {})
        for fencer_result in results.get("fencers", []):
            fencer_name = fencer_result.get("name", "")
            if query_lower in fencer_name.lower():
                # Find which pool this fencer was in (not directly available from results)
                # For now, include without pool_number from results
                # Could enhance by cross-referencing with pools
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

        return {
            "query": name,
            "matches": matches,
        }

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
