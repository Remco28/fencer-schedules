"""
Service for querying and filtering registration data for display in the web UI.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.models import Registration, Fencer, Tournament


def query_registrations(
    db: Session,
    tournament_filter: Optional[str] = None,
    fencer_filter: Optional[str] = None,
    sort_by: str = "last_seen_at",
    sort_order: str = "desc"
) -> List[Dict[str, Any]]:
    """
    Query registrations with optional filtering and sorting.

    Args:
        db: Database session
        tournament_filter: Optional case-insensitive substring filter for tournament name
        fencer_filter: Optional case-insensitive substring filter for fencer name
        sort_by: Field to sort by (fencer_name, tournament_name, last_seen_at)
        sort_order: Sort order (asc or desc)

    Returns:
        List of dictionaries containing flattened registration data
    """
    # Start with base query joining all required tables
    query = db.query(
        Registration.id,
        Fencer.name.label('fencer_name'),
        Tournament.name.label('tournament_name'),
        Tournament.date.label('tournament_date'),
        Registration.events,
        Registration.last_seen_at
    ).join(
        Fencer, Registration.fencer_id == Fencer.id
    ).join(
        Tournament, Registration.tournament_id == Tournament.id
    )

    # Apply filters
    if tournament_filter:
        query = query.filter(Tournament.name.ilike(f"%{tournament_filter}%"))

    if fencer_filter:
        query = query.filter(Fencer.name.ilike(f"%{fencer_filter}%"))

    # Apply sorting
    # Map sort_by to actual column
    sort_column_map = {
        "fencer_name": Fencer.name,
        "tournament_name": Tournament.name,
        "last_seen_at": Registration.last_seen_at
    }

    # Default to last_seen_at if invalid sort_by
    sort_column = sort_column_map.get(sort_by, Registration.last_seen_at)

    # Apply sort order
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        # Default to desc if invalid sort_order
        query = query.order_by(desc(sort_column))

    # Execute query and convert to list of dicts
    results = []
    for row in query.all():
        results.append({
            "id": row.id,
            "fencer_name": row.fencer_name,
            "tournament_name": row.tournament_name,
            "tournament_date": row.tournament_date,
            "events": row.events,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None
        })

    return results