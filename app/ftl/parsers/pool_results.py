"""Pool results JSON parser for FTL pool results data."""
import json
from typing import Optional


def parse_pool_results(
    raw: str | list[dict],
    *,
    event_id: Optional[str] = None,
    pool_round_id: Optional[str] = None
) -> dict:
    """
    Parse FTL pool results JSON to extract advancement status for all fencers.

    Args:
        raw: Either a JSON string or a pre-parsed list of fencer result dicts
        event_id: Optional event UUID for inclusion in response
        pool_round_id: Optional pool round UUID for inclusion in response

    Returns:
        dict matching PoolResults schema with keys:
            - event_id: str | None
            - pool_round_id: str | None
            - fencers: list[dict] (each matching PoolResult schema)

    Raises:
        ValueError: If raw is invalid JSON, not a list, empty, or missing required fields
    """
    # Parse JSON if needed
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")
    elif isinstance(raw, list):
        data = raw
    else:
        raise ValueError(f"Expected str or list, got {type(raw).__name__}")

    # Validate that data is a list
    if not isinstance(data, list):
        raise ValueError(f"Expected list payload, got {type(data).__name__}")

    # Validate non-empty
    if len(data) == 0:
        raise ValueError("Empty fencer list")

    # Parse each fencer
    fencers = []
    for idx, fencer_raw in enumerate(data):
        if not isinstance(fencer_raw, dict):
            raise ValueError(f"Fencer at index {idx} is not a dict")

        # Required fields
        try:
            fencer_id = fencer_raw["id"]
            name = fencer_raw["name"]
            victories = fencer_raw["v"]
            matches = fencer_raw["m"]
        except KeyError as e:
            raise ValueError(f"Missing required field at index {idx}: {e}")

        # Validate types for required fields
        if not isinstance(fencer_id, str):
            raise ValueError(f"Fencer ID at index {idx} must be a string")
        if not isinstance(name, str):
            raise ValueError(f"Name at index {idx} must be a string")
        if not isinstance(victories, int):
            raise ValueError(f"Victories (v) at index {idx} must be an integer")
        if not isinstance(matches, int):
            raise ValueError(f"Matches (m) at index {idx} must be an integer")

        # Strip and normalize name
        name = name.strip()
        fencer_id = fencer_id.strip()

        # Optional fields with normalization
        club_primary = fencer_raw.get("club1")
        if club_primary is not None:
            club_primary = club_primary.strip() if isinstance(club_primary, str) else None

        club_secondary = fencer_raw.get("club2")
        if club_secondary is not None:
            club_secondary = club_secondary.strip() if isinstance(club_secondary, str) else None

        division = fencer_raw.get("div")
        if division is not None:
            division = division.strip() if isinstance(division, str) else None

        country = fencer_raw.get("country")
        if country is not None:
            country = country.strip() if isinstance(country, str) else None

        place = fencer_raw.get("place")
        victory_ratio = fencer_raw.get("vm")
        touches_scored = fencer_raw.get("ts")
        touches_received = fencer_raw.get("tr")
        tie = fencer_raw.get("tie")

        # Indicator - convert to int if present
        indicator = fencer_raw.get("ind")
        if indicator is not None and not isinstance(indicator, int):
            try:
                indicator = int(indicator)
            except (ValueError, TypeError):
                indicator = None

        # Prediction (raw, for status derivation)
        prediction_raw = fencer_raw.get("prediction")
        if prediction_raw is not None and isinstance(prediction_raw, str):
            prediction_raw = prediction_raw.strip()
            # Convert empty string to None
            if prediction_raw == "":
                prediction_raw = None
        else:
            prediction_raw = None

        # Derive status from prediction_raw
        if prediction_raw and prediction_raw.lower() == "advanced":
            status = "advanced"
        elif prediction_raw:
            # Any other non-empty value (e.g., "Eliminated", "Cut") -> eliminated
            status = "eliminated"
        else:
            # Missing or empty
            status = "unknown"

        fencers.append({
            "fencer_id": fencer_id,
            "name": name,
            "club_primary": club_primary,
            "club_secondary": club_secondary,
            "division": division,
            "country": country,
            "place": place,
            "victories": victories,
            "matches": matches,
            "victory_ratio": victory_ratio,
            "touches_scored": touches_scored,
            "touches_received": touches_received,
            "indicator": indicator,
            "prediction_raw": prediction_raw,
            "status": status,
            "tie": tie,
        })

    return {
        "event_id": event_id,
        "pool_round_id": pool_round_id,
        "fencers": fencers,
    }
