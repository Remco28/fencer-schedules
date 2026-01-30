"""Tests for tournament service aggregation."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from app.services.tournament_service import (
    get_tournament_fencer_status,
    search_tournament_fencers,
    TTL_SHORT,
    TTL_LONG,
    _is_event_completed_from_tableau,
)
from app.ftl.client import FTLHTTPError


def _event(event_id="E" * 32, name="Event", weapon="Epee", pool_round_id="P" * 32, de_round_id="D" * 32, is_completed=False):
    return SimpleNamespace(
        event_id=event_id,
        event_name=name,
        weapon=weapon,
        pool_round_id=pool_round_id,
        de_round_id=de_round_id,
        is_completed=is_completed,
        completed_at=None,
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


def test_search_tournament_fencers_empty_query():
    result = search_tournament_fencers(1, [], "", False)
    assert result == []


def test_search_tournament_fencers_short_query():
    result = search_tournament_fencers(1, [], "A", False)
    assert result == []


def test_search_finds_reversed_name():
    """Search 'John Smith' should find 'SMITH John' (FTL format)."""
    event = _event(pool_round_id="P" * 32, de_round_id=None)
    competitors = [
        {"name": "SMITH John", "club1": "Elite"},
        {"name": "DOE Jane", "club1": "Other"},
    ]

    with patch("app.services.tournament_service.fetch_competitors_json", return_value=competitors):
        results = search_tournament_fencers(1, [event], "John Smith")

    assert len(results) == 1
    assert results[0]["name"] == "SMITH John"


def test_search_finds_first_name_only():
    """Search partial name should match."""
    event = _event(pool_round_id="P" * 32, de_round_id=None)
    competitors = [
        {"name": "SMITH John", "club1": "Elite"},
        {"name": "JOHNSON Robert", "club1": "Other"},
    ]

    with patch("app.services.tournament_service.fetch_competitors_json", return_value=competitors):
        results = search_tournament_fencers(1, [event], "John")

    assert len(results) == 2  # Matches both "John" in SMITH John and JOHNSON


def test_finished_event_shows_finished_not_waiting():
    """Fencers in completed events should show 'finished', not 'waiting'."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": [{"name": "Jane Smith", "status": "advanced"}]},
    }
    results_json = [
        {"name": "Jane Smith", "clubs": "Elite", "place": "17"},
    ]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", side_effect=FTLHTTPError("JS page")), \
         patch("app.services.tournament_service.fetch_event_results_json", return_value=results_json):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    # Fencer should be in 'finished' with place, not 'waiting' with "Advanced to DE"
    assert len(grouped["finished"]) == 1
    assert "Place: 17" in grouped["finished"][0].result
    assert len(grouped["waiting"]) == 0


# Smart Caching Tests (Phase L)

def test_completed_event_uses_long_ttl():
    """Completed events should use 24-hour TTL cache."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    event = _event(pool_round_id="P" * 32, de_round_id=None, is_completed=True)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle) as mock_fetch:
        get_tournament_fencer_status(1, "Elite", [event])

    # Verify TTL_LONG (24 hours) was passed
    mock_fetch.assert_called_once()
    call_kwargs = mock_fetch.call_args[1]
    assert call_kwargs["ttl"] == TTL_LONG


def test_active_event_uses_short_ttl():
    """Active events should use 3-minute TTL cache."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": "A1", "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    event = _event(pool_round_id="P" * 32, de_round_id=None, is_completed=False)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle) as mock_fetch:
        get_tournament_fencer_status(1, "Elite", [event])

    # Verify TTL_SHORT (3 minutes) was passed
    mock_fetch.assert_called_once()
    call_kwargs = mock_fetch.call_args[1]
    assert call_kwargs["ttl"] == TTL_SHORT


def test_event_marked_completed_when_results_fetched():
    """Event should be marked as completed when results endpoint succeeds."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": [{"name": "Jane Smith", "status": "advanced"}]},
    }
    results_json = [
        {"name": "Jane Smith", "clubs": "Elite", "place": "1"},
    ]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32, is_completed=False)
    mock_db = MagicMock()

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", side_effect=FTLHTTPError("JS page")), \
         patch("app.services.tournament_service.fetch_event_results_json", return_value=results_json):
        get_tournament_fencer_status(1, "Elite", [event], db=mock_db)

    # Event should be marked as completed
    assert event.is_completed is True
    assert event.completed_at is not None
    mock_db.add.assert_called_once_with(event)


def test_is_event_completed_from_tableau_final_complete():
    """Event is complete when Final match has status='complete'."""
    matches = [
        {"round": "32", "status": "complete"},
        {"round": "16", "status": "complete"},
        {"round": "8", "status": "complete"},
        {"round": "QF", "status": "complete"},
        {"round": "SF", "status": "complete"},
        {"round": "F", "status": "complete"},  # Gold medal bout done
    ]
    assert _is_event_completed_from_tableau(matches) is True


def test_is_event_completed_from_tableau_final_in_progress():
    """Event is NOT complete when Final match is still in progress."""
    matches = [
        {"round": "32", "status": "complete"},
        {"round": "16", "status": "complete"},
        {"round": "F", "status": "in_progress"},  # Final still going
    ]
    assert _is_event_completed_from_tableau(matches) is False


def test_is_event_completed_from_tableau_no_final():
    """Event is NOT complete when there's no Final match yet."""
    matches = [
        {"round": "32", "status": "complete"},
        {"round": "16", "status": "in_progress"},
    ]
    assert _is_event_completed_from_tableau(matches) is False


def test_event_marked_completed_when_final_complete():
    """Event should be marked as completed when Final bout is done in tableau."""
    event = _event(pool_round_id=None, de_round_id="D" * 32, is_completed=False)
    matches = [
        {"round": "F", "status": "complete", "winner": "A",
         "name_a": "Gold Winner", "club_a": "Elite",
         "name_b": "Silver Runner", "club_b": "Other"},
    ]
    mock_db = MagicMock()

    with patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": matches}):
        get_tournament_fencer_status(1, "Elite", [event], db=mock_db)

    # Event should be marked as completed
    assert event.is_completed is True
    assert event.completed_at is not None
    mock_db.add.assert_called_once_with(event)
