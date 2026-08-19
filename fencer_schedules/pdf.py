from __future__ import annotations

import re
from collections import defaultdict

from fpdf import FPDF

from fencer_schedules.config import Settings
from fencer_schedules.models import Tournament
from fencer_schedules.schedule import visible_events


def render_pdf(tournament: Tournament, settings: Settings) -> bytes:
    events = visible_events(tournament, settings)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, _latin(tournament.name))
    pdf.set_font("Helvetica", size=11)
    if tournament.venue:
        pdf.cell(0, 6, _latin(tournament.venue), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _latin(settings.club_name), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    by_day: dict = defaultdict(list)
    for event in events:
        by_day[event.day].append(event)

    for day in sorted(by_day):
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, day.strftime("%A, %B %-d"), new_x="LMARGIN", new_y="NEXT")
        for event in by_day[day]:
            pdf.set_font("Helvetica", "B", 11)
            clock = ""
            if event.clock:
                clock = f" — {event.clock.strftime('%-I:%M %p')}"
            pdf.cell(0, 6, _latin(f"{event.name}{clock}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=11)
            if not event.fencers:
                pdf.cell(0, 5, "  (no club names available)", new_x="LMARGIN", new_y="NEXT")
            for fencer in event.fencers:
                pdf.cell(0, 5, _latin(f"  {fencer.name}  ·  {fencer.club}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    return bytes(pdf.output())


def filename_for(tournament: Tournament) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", tournament.name.casefold()).strip("-")
    return f"elite-fc-{slug}-{tournament.start_date.isoformat()}.pdf"


def _latin(value: str) -> str:
    return (
        value.replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
