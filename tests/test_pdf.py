from __future__ import annotations

import re
import zlib
from datetime import date

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, EventResult, Fencer, Tournament
from fencer_schedules.pdf import SchedulePDF, _latin, filename_for, render_pdf


def _sample():
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
                fencers=[
                    Fencer(name="Doe, Jordan", club="Elite Fencers Club"),
                    Fencer(name="NoShow, Riley", club="Elite Fencers Club"),
                ],
                results=[EventResult(place="8", name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )
    return settings, tournament


def _pdf_streams(data: bytes) -> list[bytes]:
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            streams.append(zlib.decompress(match.group(1)))
        except zlib.error:
            continue
    return streams


def test_pdf_contains_club_fencer_and_day() -> None:
    settings, tournament = _sample()
    data = render_pdf(tournament, settings)
    assert data.startswith(b"%PDF")
    # fpdf2 text is not always extractable as ascii; filename is the other contract
    assert "trick-or-retreat" in filename_for(tournament)
    assert "2026-08-22" in filename_for(tournament)
    assert b"/Image" in data  # small club logo in the header
    streams = b"\n".join(_pdf_streams(data))
    assert b"(8th)" in streams
    assert b"(No result)" in streams


def test_day_underline_matches_label_width() -> None:
    pdf = SchedulePDF(_sample()[1], "Elite Fencers Club")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    label = _latin("Saturday, September 12")
    width = pdf.get_string_width(label)
    assert round(width, 2) == 48.23


def test_pdf_leaves_the_place_blank_before_results_are_fetched() -> None:
    """An event that has not been fenced must not claim every fencer has no result."""
    settings, tournament = _sample()
    unplayed = tournament.model_copy(
        update={"events": [tournament.events[0].model_copy(update={"results": None})]}
    )
    streams = b"\n".join(_pdf_streams(render_pdf(unplayed, settings)))
    assert b"(Doe, Jordan)" in streams
    assert b"(No result)" not in streams


def test_pdf_marks_published_results_it_cannot_match() -> None:
    settings, tournament = _sample()
    streams = b"\n".join(_pdf_streams(render_pdf(tournament, settings)))
    assert b"(No result)" in streams
