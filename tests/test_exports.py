from __future__ import annotations

import csv
import io
from datetime import date, time

from fencer_schedules.config import Settings
from fencer_schedules.exports import csv_bytes, text_version
from fencer_schedules.models import Event, Fencer, Tournament


def _tournament() -> Tournament:
    return Tournament(
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
                clock=time(8, 0),
                fencers=[Fencer(name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )


def _settings() -> Settings:
    return Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])


def test_csv_bytes_has_header_and_row() -> None:
    data = csv_bytes(_tournament(), _settings())
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert rows[0] == ["day", "time", "event", "fencer", "club"]
    assert ["2026-08-22", "08:00", "Junior Men's Epee", "Doe, Jordan", "Elite Fencers Club"] in rows


def test_text_version_has_day_and_fencer() -> None:
    text = text_version(_tournament(), _settings())
    assert "Trick or Retreat ROC / RJCC" in text
    assert "Saturday, August 22" in text
    assert "8:00 AM Junior Men's Epee" in text
    assert "• Doe, Jordan (Elite Fencers Club)" in text
