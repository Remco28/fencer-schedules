"""Tests for tournament service aggregation."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services.tournament_service import get_tournament_fencer_status
from app.ftl.client import FTLHTTPError


def _event(event_id="E" * 32, name="Event", weapon="Epee", pool_round_id="P" * 32, de_round_id="D" * 32):
    return SimpleNamespace(
        event_id=event_id,
        event_name=name,
        weapon=weapon,
        pool_round_id=pool_round_id,
        de_round_id=de_round_id,
    )


def test_get_tournament_fencer_status_empty_club():
    grouped = get_tournament_fencer_status(1, "", [], force_refresh=False)
    assert grouped == {"active": [], "waiting": [], "finished": []}


def test_pools_active_fencer():
    bundle = {
        "pools": [
            {"pool_number": 3, "strip": "A5", "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    event = _event(pool_round_id="P" * 32, de_round_id=None)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["active"]) == 1
    assert grouped["active"][0].name == "Jane Smith"
    assert grouped["active"][0].phase == "pools"


def test_pools_eliminated_fencer():
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "Bob Jones", "club": "Elite"}]},
        ],
        "results": {"fencers": [{"name": "Bob Jones", "status": "eliminated"}]},
    }
    event = _event(pool_round_id="P" * 32, de_round_id=None)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["finished"]) == 1
    assert grouped["finished"][0].result == "Eliminated"


def test_de_active_fencer():
    event = _event(pool_round_id=None, de_round_id="D" * 32)
    matches = [{
        "round": "32",
        "status": "in_progress",
        "winner": None,
        "name_a": "Jane Smith",
        "club_a": "Elite",
        "name_b": "Other",
        "club_b": "Other",
    }]

    with patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
        patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["active"]) == 1
    assert grouped["active"][0].phase == "de"


def test_handles_fetch_errors():
    event = _event(pool_round_id="P" * 32, de_round_id=None)

    with patch("app.services.tournament_service.fetch_pools_bundle", side_effect=FTLHTTPError("fail")):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["waiting"]) == 1
    assert grouped["waiting"][0].error
