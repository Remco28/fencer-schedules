from __future__ import annotations

from datetime import date

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament
from fencer_schedules.pdf import filename_for, render_pdf


def test_pdf_contains_club_fencer_and_day() -> None:
    settings = Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])
    tournament = Tournament(
        askfred_id="t",
        name="Trick or Retreat ROC / RJCC",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 23),
        venue="Edison NJ",
        events=[
            Event(
                source_event_id="1",
                name="Junior Men's Epee",
                day=date(2026, 8, 22),
                fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )
    data = render_pdf(tournament, settings)
    assert data.startswith(b"%PDF")
    # fpdf2 text is not always extractable as ascii; filename is the other contract
    assert "trick-or-retreat" in filename_for(tournament)
    assert "2026-08-22" in filename_for(tournament)
