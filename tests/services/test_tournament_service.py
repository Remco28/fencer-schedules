"""Tests for tournament service aggregation."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from app.services.tournament_service import (
    get_tournament_fencer_status,
    search_tournament_fencers,
    TTL_SHORT,
    TTL_LONG,
    _is_event_completed_from_tableau,
    _merge_status,
    FencerStatus,
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
    assert grouped == {"active": [], "up_next": [], "waiting": [], "finished": []}


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


# Merge Status Priority Tests

def test_merge_status_active_beats_waiting_across_phases():
    """Active pool status should beat waiting DE status, regardless of phase."""
    pool_active = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="active",
        phase="pools",
        strip="A5",
    )
    de_waiting = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="waiting",
        phase="de",
        de_round="32",
    )

    # Pool active should win even though DE has higher phase priority
    result = _merge_status(pool_active, de_waiting)
    assert result.activity == "active"
    assert result.phase == "pools"
    assert result.strip == "A5"

    # Verify the reverse order also works
    result = _merge_status(de_waiting, pool_active)
    assert result.activity == "active"
    assert result.phase == "pools"


def test_merge_status_de_active_beats_pool_waiting():
    """Active DE status should beat waiting pool status."""
    de_active = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="active",
        phase="de",
        de_round="16",
    )
    pool_waiting = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="waiting",
        phase="pools",
    )

    result = _merge_status(pool_waiting, de_active)
    assert result.activity == "active"
    assert result.phase == "de"


def test_merge_status_same_activity_uses_phase_rank():
    """When both have same activity, higher phase wins."""
    de_waiting = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="waiting",
        phase="de",
    )
    pool_waiting = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="waiting",
        phase="pools",
    )

    # DE (phase=2) should beat pools (phase=1) when both are waiting
    result = _merge_status(pool_waiting, de_waiting)
    assert result.phase == "de"


def test_merge_status_finished_beats_active():
    """Finished DE status should beat active pool status."""
    pool_active = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="active",
        phase="pools",
        strip="A5",
    )
    de_finished = FencerStatus(
        name="Jane Smith",
        event_id="E" * 32,
        event_name="Event",
        weapon="Epee",
        activity="finished",
        phase="de",
        de_round="8",
        result="Eliminated",
    )

    result = _merge_status(pool_active, de_finished)
    assert result.activity == "finished"
    assert result.phase == "de"

    result = _merge_status(de_finished, pool_active)
    assert result.activity == "finished"
    assert result.phase == "de"


def test_pool_active_beats_de_waiting_integrated():
    """Integration test: Pool strip assignment should show fencer as Active, not Waiting."""
    bundle = {
        "pools": [
            {"pool_number": 3, "strip": "A5", "fencers": [{"name": "Jane Smith", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    # DE match exists but is pending (no strip)
    de_matches = [{
        "round": "32",
        "status": "pending",
        "winner": None,
        "name_a": "Jane Smith",
        "club_a": "Elite",
        "name_b": "Other Fencer",
        "club_b": "Other",
        "strip": None,
    }]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    # Should be Active (from pools), not Waiting (from DE pending)
    assert len(grouped["active"]) == 1
    assert grouped["active"][0].activity == "active"
    assert grouped["active"][0].strip == "A5"
    assert len(grouped["waiting"]) == 0


def test_de_matches_use_known_club_names_when_club_missing():
    """DE matches without club info should still be included for known club fencers."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": "5", "fencers": [{"name": "MENDEZ Brendan", "club": "Elite FC"}]},
        ],
        "results": {"fencers": []},
    }
    de_matches = [{
        "round": "8",
        "status": "complete",
        "winner": "A",
        "name_a": "PEARLY Aiden",
        "club_a": None,
        "score_a": 15,
        "name_b": "MENDEZ Brendan",
        "club_b": None,
        "score_b": 7,
        "strip": "5",
    }]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["finished"]) == 1
    assert grouped["finished"][0].name == "MENDEZ Brendan"
    assert grouped["finished"][0].activity == "finished"


def test_de_pending_without_strip_is_up_next():
    """Pending DE matches with both fencers and no strip should be up_next."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "HENNEMAN Graham", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    de_matches = [{
        "round": "F",
        "status": "pending",
        "winner": None,
        "name_a": "HENNEMAN Graham",
        "club_a": None,
        "name_b": "LAVIN Ethan",
        "club_b": None,
        "strip": None,
    }]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["active"]) == 0
    assert len(grouped["up_next"]) == 1
    assert grouped["up_next"][0].name == "HENNEMAN Graham"
    assert grouped["up_next"][0].activity == "up_next"


def test_de_final_pending_beats_completed_sf_with_strip():
    """Final pending should be preferred over completed SF even if SF has strip."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "HENNEMAN Graham", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    de_matches = [
        {
            "round": "SF",
            "status": "complete",
            "winner": "A",
            "name_a": "HENNEMAN Graham",
            "club_a": None,
            "name_b": "MENDEZ Brendan",
            "club_b": None,
            "score_a": 15,
            "score_b": 13,
            "strip": "5",
        },
        {
            "round": "F",
            "status": "pending",
            "winner": None,
            "name_a": "HENNEMAN Graham",
            "club_a": None,
            "name_b": None,
            "club_b": None,
            "strip": None,
        },
    ]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["up_next"]) == 1
    assert grouped["up_next"][0].name == "HENNEMAN Graham"
    assert grouped["up_next"][0].de_round == "F"


def test_sf_winner_up_next_when_final_missing_name():
    """SF winner should be up_next if final exists but doesn't include them yet."""
    bundle = {
        "pools": [
            {"pool_number": 1, "strip": None, "fencers": [{"name": "LAVIN Ethan", "club": "Elite"}]},
        ],
        "results": {"fencers": []},
    }
    de_matches = [
        {
            "round": "SF",
            "status": "complete",
            "winner": "A",
            "name_a": "LAVIN Ethan",
            "club_a": None,
            "name_b": "SINGH Vir",
            "club_b": None,
            "score_a": 15,
            "score_b": 9,
            "strip": "4",
        },
        {
            "round": "F",
            "status": "pending",
            "winner": None,
            "name_a": "HENNEMAN Graham",
            "club_a": None,
            "name_b": None,
            "club_b": None,
            "strip": None,
        },
    ]
    event = _event(pool_round_id="P" * 32, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_pools_bundle", return_value=bundle), \
         patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["up_next"]) == 1
    assert grouped["up_next"][0].name == "LAVIN Ethan"
    assert grouped["up_next"][0].de_round == "F"


def test_results_override_incomplete_tableau():
    """If tableau isn't complete but results exist, use results and mark finished."""
    de_matches = [
        {
            "round": "F",
            "status": "pending",
            "winner": None,
            "name_a": "HENNEMAN Graham",
            "club_a": None,
            "name_b": None,
            "club_b": None,
            "strip": None,
        },
    ]
    results = [
        {"name": "HENNEMAN Graham", "place": "1", "clubs": "Elite FC"},
        {"name": "LAVIN Ethan", "place": "2", "clubs": "Elite FC"},
    ]
    event = _event(pool_round_id=None, de_round_id="D" * 32)

    with patch("app.services.tournament_service.fetch_tableau_raw", return_value="<html></html>"), \
         patch("app.services.tournament_service.parse_de_tableau", return_value={"matches": de_matches}), \
         patch("app.services.tournament_service.fetch_event_results_json", return_value=results), \
         patch("app.services.tournament_service.fetch_competitors_json", return_value=[{"name": "HENNEMAN Graham"}, {"name": "LAVIN Ethan"}]):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["finished"]) == 2
    assert all(status.phase == "complete" for status in grouped["finished"])


def test_results_used_when_no_de_round():
    """If no DE round exists, results should still populate finished statuses."""
    results = [
        {"name": "HENNEMAN Graham", "place": "1", "clubs": "Elite FC"},
        {"name": "LAVIN Ethan", "place": "2", "clubs": "Elite FC"},
    ]
    event = _event(pool_round_id=None, de_round_id=None)

    with patch("app.services.tournament_service.fetch_event_results_json", return_value=results), \
         patch("app.services.tournament_service.fetch_competitors_json", return_value=[{"name": "HENNEMAN Graham"}, {"name": "LAVIN Ethan"}]):
        grouped = get_tournament_fencer_status(1, "Elite", [event])

    assert len(grouped["finished"]) == 2
