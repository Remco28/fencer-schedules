from __future__ import annotations

from pathlib import Path

from fencer_schedules.sources.askfred_prereg import parse_preregistrations

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_preregistrations_groups_by_event() -> None:
    html = (FIXTURES / "askfred_prereg_wanglei.html").read_text()
    by_event = parse_preregistrations(html)
    assert "Anderson, Connor" in [f.name for f in by_event["Y14 Mixed Epee"]]
    assert any(f.club == "Elite Fencers Club" for f in by_event["Y14 Mixed Epee"])
    assert [f.name for f in by_event["Senior Mixed Epee"]] == ["Sun, Kang"]
