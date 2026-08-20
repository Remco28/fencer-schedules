from __future__ import annotations

from datetime import time
from pathlib import Path

from fencer_schedules.sources.askfred_prereg import (
    parse_preregistration_clocks,
    parse_preregistrations,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_preregistrations_groups_by_event() -> None:
    html = (FIXTURES / "askfred_prereg_wanglei.html").read_text()
    by_event = parse_preregistrations(html)
    assert "Anderson, Connor" in [f.name for f in by_event["Y14 Mixed Epee"]]
    assert any(f.club == "Elite Fencers Club" for f in by_event["Y14 Mixed Epee"])
    assert [f.name for f in by_event["Senior Mixed Epee"]] == ["Sun, Kang"]


def test_parse_checkin_clocks() -> None:
    html = (FIXTURES / "askfred_prereg_wanglei.html").read_text()
    clocks = parse_preregistration_clocks(html)
    assert clocks["Y14 Mixed Epee"] == time(9, 30)
    assert clocks["Senior Mixed Epee"] == time(14, 0)
