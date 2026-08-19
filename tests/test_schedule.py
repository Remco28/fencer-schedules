from __future__ import annotations

from datetime import date

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament
from fencer_schedules.schedule import (
    add_manual,
    search_loaded_fencers,
    track_named,
    untrack_named,
    visible_events,
)


def _settings() -> Settings:
    return Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])


def _tournament() -> Tournament:
    return Tournament(
        askfred_id="t1",
        name="Sample",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 23),
        names_available=True,
        events=[
            Event(
                source_event_id="1",
                name="Junior Men’s Epee",
                day=date(2026, 8, 22),
                fencers=[
                    Fencer(name="Doe, Jordan", club="Elite Fencers Club"),
                    Fencer(name="Albrecht-Smith, Anne", club="Manchen Academy Of Fencing"),
                ],
            ),
            Event(
                source_event_id="2",
                name="Cadet Women’s Foil",
                day=date(2026, 8, 22),
                fencers=[Fencer(name="Other, Kid", club="Some Club")],
            ),
        ],
    )


def test_only_our_club_appears_under_events() -> None:
    visible = visible_events(_tournament(), _settings())
    names = [f.name for e in visible for f in e.fencers]
    assert names == ["Doe, Jordan"]
    assert all(e.name != "Cadet Women’s Foil" for e in visible)


def test_manual_add_keeps_other_club_label() -> None:
    updated = add_manual(_tournament(), "Albrecht")
    visible = visible_events(updated, _settings())
    fencer = next(f for e in visible for f in e.fencers if "Albrecht" in f.name)
    assert fencer.source == "manual"
    assert fencer.club == "Manchen Academy Of Fencing"


def test_search_finds_non_club_fencer() -> None:
    hits = search_loaded_fencers(_tournament(), "albrecht")
    assert hits[0].name.startswith("Albrecht")


def test_untrack_hides_club_and_manual() -> None:
    settings = _settings()
    tracked = add_manual(_tournament(), "Albrecht", settings)
    hidden = untrack_named(tracked, "Doe, Jordan", "Elite Fencers Club")
    hidden = untrack_named(hidden, "Albrecht-Smith, Anne", "Manchen Academy Of Fencing")
    names = [f.name for e in visible_events(hidden, settings) for f in e.fencers]
    assert names == []


def test_track_named_adds_other_club() -> None:
    settings = _settings()
    updated = track_named(
        _tournament(), "Albrecht-Smith, Anne", "Manchen Academy Of Fencing", settings
    )
    names = [f.name for e in visible_events(updated, settings) for f in e.fencers]
    assert "Albrecht-Smith, Anne" in names


def test_local_keeps_empty_events() -> None:
    local = _tournament().model_copy(update={"names_available": False, "events": [
        Event(source_event_id="9", name="Senior Mixed Epee", day=date(2026, 8, 29), fencers=[])
    ]})
    visible = visible_events(local, _settings())
    assert len(visible) == 1
    assert visible[0].fencers == []
