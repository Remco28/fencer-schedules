from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from fpdf import FPDF

from fencer_schedules.config import Settings
from fencer_schedules.models import Tournament
from fencer_schedules.schedule import visible_events

NAVY = (10, 22, 40)
GOLD = (212, 175, 55)
TEAL = (15, 118, 110)
MUTED = (100, 116, 139)
RULE = (226, 232, 240)
INK = (30, 41, 59)


class SchedulePDF(FPDF):
    def __init__(self, tournament: Tournament, club: str) -> None:
        super().__init__(format="Letter")
        self.tournament = tournament
        self.club = club
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)

    def header(self) -> None:
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 28, "F")
        self.set_xy(16, 7)
        self.set_text_color(*GOLD)
        self.set_font("Helvetica", "B", 8)
        self.cell(0, 4, _latin(self.club.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_x(16)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 7, _latin(self.tournament.name), new_x="LMARGIN", new_y="NEXT")
        self.set_y(32)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*RULE)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        left = f"Club schedule  ·  {self.club}"
        right = f"Page {self.page_no()}"
        self.cell(0, 6, _latin(left), align="L")
        self.set_xy(16, -12)
        self.cell(0, 6, right, align="R")


def render_pdf(tournament: Tournament, settings: Settings) -> bytes:
    events = visible_events(tournament, settings)
    pdf = SchedulePDF(tournament, settings.club_name)
    pdf.add_page()

    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", size=10)
    if tournament.venue:
        pdf.multi_cell(0, 5, _latin(tournament.venue))
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, _latin(_dates(tournament.start_date, tournament.end_date)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    by_day: dict[date, list] = defaultdict(list)
    for event in events:
        by_day[event.day].append(event)

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    name_w = usable * 0.48
    club_w = usable * 0.52

    for day in sorted(by_day):
        if pdf.get_y() > pdf.h - 40:
            pdf.add_page()
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, day.strftime("%A, %B %d").replace(" 0", " "), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(0.6)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + 28, y)
        pdf.ln(3)

        for event in by_day[day]:
            need = 16 + 5 * max(len(event.fencers), 1)
            if pdf.get_y() + need > pdf.h - 20:
                pdf.add_page()
            clock = event.clock.strftime("%I:%M %p").lstrip("0") if event.clock else ""
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*GOLD)
            if clock:
                pdf.cell(22, 5, clock)
            else:
                pdf.cell(22, 5, "")
            pdf.set_text_color(*NAVY)
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5, _latin(event.name))

            if not event.fencers:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*MUTED)
                pdf.cell(0, 5, "    No tracked fencers", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                continue

            pdf.set_x(pdf.l_margin + 22)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*MUTED)
            pdf.cell(name_w - 8, 4, "FENCER")
            pdf.cell(club_w, 4, "CLUB", new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*RULE)
            pdf.set_line_width(0.2)
            pdf.line(pdf.l_margin + 22, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())

            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(*INK)
            for fencer in event.fencers:
                pdf.set_x(pdf.l_margin + 22)
                pdf.cell(name_w - 8, 5, _latin(fencer.name))
                pdf.cell(club_w, 5, _latin(fencer.club), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    return bytes(pdf.output())


def filename_for(tournament: Tournament) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", tournament.name.casefold()).strip("-")
    return f"elite-fc-{slug}-{tournament.start_date.isoformat()}.pdf"


def _dates(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%B %d, %Y").replace(" 0", " ")
    if start.month == end.month and start.year == end.year:
        return f"{start.strftime('%B')} {start.day}-{end.day}, {end.year}"
    return f"{start.strftime('%B %d').replace(' 0', ' ')} - {end.strftime('%B %d, %Y').replace(' 0', ' ')}"


def _latin(value: str) -> str:
    return (
        value.replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
