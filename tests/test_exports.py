from __future__ import annotations

import csv
import io
from datetime import date, time

from fencer_schedules.config import Settings
from fencer_schedules.exports import csv_bytes, text_version
from fencer_schedules.models import UNKNOWN_DAY, Event, EventResult, Fencer, Tournament


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
                results=[EventResult(place="8", name="Doe, Jordan", club="Elite Fencers Club")],
            )
        ],
    )


def _settings() -> Settings:
    return Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])


def test_csv_bytes_has_header_and_row() -> None:
    data = csv_bytes(_tournament(), _settings())
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert rows[0] == ["day", "time", "event", "fencer", "club", "final_place"]
    assert ["2026-08-22", "08:00", "Junior Men's Epee", "Doe, Jordan", "Elite Fencers Club", "8th"] in rows


def test_text_version_has_day_and_fencer() -> None:
    text = text_version(_tournament(), _settings())
    assert "Trick or Retreat ROC / RJCC" in text
    assert "Saturday, August 22" in text
    assert "8:00 AM Junior Men's Epee" in text
    assert "• Doe, Jordan (Elite Fencers Club) — 8th" in text


def _event_with(fencers, results) -> Tournament:
    return Tournament(
        askfred_id="t",
        name="Trick or Retreat ROC / RJCC",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 22),
        events=[
            Event(
                source_event_id="1",
                name="Junior Men's Epee",
                day=date(2026, 8, 22),
                fencers=fencers,
                results=results,
            )
        ],
    )


def test_exports_word_places_the_same_way_as_the_app() -> None:
    tournament = _event_with(
        [
            Fencer(name="Doe, Jordan", club="Elite Fencers Club"),
            Fencer(name="Ng, Nico", club="Elite Fencers Club"),
        ],
        [EventResult(place="25.5", name="Doe, Jordan", club="Elite Fencers Club")],
    )
    rows = list(csv.reader(io.StringIO(csv_bytes(tournament, _settings()).decode("utf-8"))))
    places = {row[3]: row[5] for row in rows[1:]}
    assert places["Doe, Jordan"] == "Tied for 25th"
    assert places["Ng, Nico"] == "No result"

    text = text_version(tournament, _settings())
    assert "• Doe, Jordan (Elite Fencers Club) — Tied for 25th" in text
    assert "• Ng, Nico (Elite Fencers Club) — No result" in text


def test_exports_stay_blank_before_results_are_published() -> None:
    tournament = _event_with(
        [Fencer(name="Doe, Jordan", club="Elite Fencers Club")], results=None
    )
    rows = list(csv.reader(io.StringIO(csv_bytes(tournament, _settings()).decode("utf-8"))))
    assert rows[1][5] == ""
    assert "No result" not in text_version(tournament, _settings())


def test_exports_mark_a_day_the_source_never_published() -> None:
    tournament = _event_with([Fencer(name="Doe, Jordan", club="Elite Fencers Club")], None)
    tournament = tournament.model_copy(
        update={
            "events": [
                tournament.events[0].model_copy(
                    update={"day": UNKNOWN_DAY, "day_unknown": True}
                )
            ]
        }
    )
    rows = list(csv.reader(io.StringIO(csv_bytes(tournament, _settings()).decode("utf-8"))))
    assert rows[1][0] == ""
    assert "Day TBD" in text_version(tournament, _settings())
