from __future__ import annotations

import csv
import io
from datetime import time

from fencer_schedules.config import Settings
from fencer_schedules.models import Event, Fencer, Tournament
from fencer_schedules.schedule import result_place, visible_events


def _place(event: Event, fencer: Fencer) -> str:
    return result_place(event, fencer) or ""


def csv_bytes(tournament: Tournament, settings: Settings) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["day", "time", "event", "fencer", "club", "final_place"])
    for event in visible_events(tournament, settings):
        day = event.day.isoformat()
        clock = event.clock.strftime("%H:%M") if event.clock else ""
        for fencer in event.fencers:
            writer.writerow([day, clock, event.name, fencer.name, fencer.club, _place(event, fencer)])
    return buffer.getvalue().encode("utf-8")


def text_version(tournament: Tournament, settings: Settings) -> str:
    lines: list[str] = []
    header = tournament.name
    if tournament.venue:
        header += f" — {tournament.venue}"
    lines.append(header)
    current_day = None
    for event in visible_events(tournament, settings):
        if event.day != current_day:
            current_day = event.day
            lines.append("")
            lines.append(event.day.strftime("%A, %B %d").replace(" 0", " "))
        clock = event.clock.strftime("%-I:%M %p").lstrip("0") if event.clock else "TBD"
        lines.append("")
        lines.append(f"{clock} {event.name}")
        for fencer in event.fencers:
            place = _place(event, fencer)
            suffix = f" — {place} place" if place else ""
            lines.append(f"  • {fencer.name} ({fencer.club}){suffix}")
    return "\n".join(lines).strip() + "\n"


def filename_for(tournament: Tournament, suffix: str) -> str:
    from fencer_schedules.pdf import filename_for as pdf_name

    return pdf_name(tournament).replace(".pdf", suffix)
