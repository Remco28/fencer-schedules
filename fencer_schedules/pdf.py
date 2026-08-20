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
MUTED = (100, 116, 139)
RULE = (226, 232, 240)
INK = (30, 41, 59)


class SchedulePDF(FPDF):
    def __init__(self, tournament: Tournament, club: str) -> None:
        super().__init__(format="Letter")
        self.tournament = tournament
        self.club = club
        self.day_label = ""
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(16, 34, 16)

    def header(self) -> None:
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 28, "F")
        self.set_xy(16, 7)
        self.set_text_color(*GOLD)
        self.set_font("Helvetica", "B", 8)
        self.cell(90, 4, _latin(self.club.upper()))
        self.set_font("Helvetica", size=8)
        self.set_text_color(203, 213, 225)
        self.cell(0, 4, _latin(_dates(self.tournament.start_date, self.tournament.end_date)), align="R")
        self.ln(5)
        self.set_x(16)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 7, _latin(self.tournament.name), new_x="LMARGIN", new_y="NEXT")
        self.set_y(34)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*RULE)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        left = self.day_label or f"Club schedule  ·  {self.club}"
        self.cell(0, 6, _latin(left), align="L")
        self.set_xy(16, -12)
        self.cell(0, 6, f"Page {self.page_no()}", align="R")


def render_pdf(tournament: Tournament, settings: Settings) -> bytes:
    events = visible_events(tournament, settings)
    pdf = SchedulePDF(tournament, settings.club_name)

    by_day: dict[date, list] = defaultdict(list)
    for event in events:
        by_day[event.day].append(event)

    days = sorted(by_day)
    usable = pdf.w - 16 - 16
    name_w = usable * 0.50
    club_w = usable * 0.50
    indent = 22

    for index, day in enumerate(days):
        pdf.day_label = day.strftime("%A, %B %d").replace(" 0", " ")
        pdf.add_page()
        if index == 0 and tournament.venue:
            pdf.set_text_color(*INK)
            pdf.set_font("Helvetica", size=10)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _latin(tournament.venue))
            pdf.ln(2)

        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, pdf.day_label, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(0.6)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + 28, y)
        pdf.ln(4)

        for event in by_day[day]:
            need = 14 + 5 * max(len(event.fencers), 1)
            if pdf.get_y() + need > pdf.h - 22:
                pdf.add_page()
            clock = event.clock.strftime("%I:%M %p").lstrip("0") if event.clock else ""
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*GOLD)
            pdf.cell(indent, 5, clock)
            pdf.set_text_color(*NAVY)
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5, _latin(event.name))

            if not event.fencers:
                pdf.set_x(pdf.l_margin + indent)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*MUTED)
                pdf.cell(0, 5, "No tracked fencers", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                continue

            pdf.set_draw_color(*RULE)
            pdf.set_line_width(0.2)
            pdf.line(pdf.l_margin + indent, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(1)
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(*INK)
            for fencer in event.fencers:
                pdf.set_x(pdf.l_margin + indent)
                pdf.cell(name_w - 4, 5, _latin(fencer.name))
                pdf.cell(club_w, 5, _latin(fencer.club), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    if not days:
        pdf.add_page()

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
