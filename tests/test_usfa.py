from __future__ import annotations

import json
from pathlib import Path

from fencer_schedules.sources.usfa import parse_entrants_table, parse_tournament_events

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_events_by_day() -> None:
    html = (FIXTURES / "usfa_tournament_12013.html").read_text()
    events = parse_tournament_events(html, year=2026)
    assert any(e.source_event_id == "72823" and e.day.isoformat() == "2026-08-22" for e in events)
    assert any(e.source_event_id == "72829" and e.day.isoformat() == "2026-08-23" for e in events)
    assert any("Junior" in e.name for e in events)


def test_parse_events_reads_close_of_registration_clock() -> None:
    html = (FIXTURES / "usfa_tournament_12013.html").read_text()
    events = {e.source_event_id: e for e in parse_tournament_events(html, year=2026)}
    junior = events["72823"]
    assert junior.clock is not None
    assert junior.clock.hour == 8
    assert junior.clock.minute == 0
    assert junior.clock_label is None
    noon = events["72806"]
    assert noon.clock is not None
    assert noon.clock.hour == 12
    late = events["72829"]
    assert late.clock is not None
    assert late.clock.hour == 10
    assert late.clock.minute == 30


def test_parse_entrants_reads_club_and_name() -> None:
    payload = json.loads((FIXTURES / "usfa_entrants_72823.json").read_text())
    fencers = parse_entrants_table(payload["entrants_table"])
    assert any(f.club == "Elite Fencers Club" and f.name == "Doe, Jordan" for f in fencers)
    assert any(f.name == "Albrecht-Smith, Anne" for f in fencers)
    assert any(f.membership_id == "100000001" for f in fencers)
