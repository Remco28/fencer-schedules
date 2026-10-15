from __future__ import annotations

import re
from datetime import date, datetime

from fencer_schedules.club import is_our_club
from fencer_schedules.config import DEFAULT_ALERT_RECIPIENT, Settings
from fencer_schedules.db import Store
from fencer_schedules.models import Event, Tournament
from fencer_schedules.notify import SKIPPED, send_digest
from fencer_schedules.schedule import data_as_of, day_label, is_tracked, result_label, visible_events

DIGEST_RECIPIENT_KEY = "digest_recipient"
DIGEST_TIME_KEY = "digest_time"
DIGEST_SENT_ON_KEY = "digest_sent_on"
DEFAULT_DIGEST_TIME = "07:00"

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_digest_time(raw: str | None) -> str | None:
    """Return a single HH:MM, or None when the value is blank or invalid."""
    value = (raw or "").strip()
    return value if _TIME_RE.match(value) else None


def digest_time_for(store: Store) -> str:
    """Saved HH:MM, or 07:00 when unset or invalid."""
    return parse_digest_time(store.get_setting(DIGEST_TIME_KEY, "")) or DEFAULT_DIGEST_TIME


def digest_recipients_for(store: Store) -> list[str]:
    raw = store.get_setting(DIGEST_RECIPIENT_KEY, DEFAULT_ALERT_RECIPIENT)
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def digest_due(store: Store, now: datetime) -> bool:
    """True inside the ±30 minute window, and not already sent today."""
    from fencer_schedules.monitor import is_check_hour

    if not is_check_hour(now, [digest_time_for(store)]):
        return False
    return store.get_setting(DIGEST_SENT_ON_KEY, "") != now.date().isoformat()


def _clock(event: Event) -> str:
    if not event.clock:
        return ""
    return event.clock.strftime("%-I:%M %p").lstrip("0")


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _place(event: Event, fencer) -> str:
    if event.results is None:
        return ""
    return result_label(event, fencer) or "No result"


def watched_tournaments(store: Store) -> list[Tournament]:
    """Loaded tournaments with a club or event watch, soonest first."""
    watched = {watch.askfred_id for watch in store.watches()}
    return [t for t in store.list() if t.askfred_id in watched]


def build_daily_digest(
    tournaments: list[Tournament],
    settings: Settings,
    today: date,
) -> tuple[str, str, str]:
    """Snapshot of every watched tournament, including ones nobody entered."""
    subject = f"Club schedule · {today.strftime('%A, %B %-d')}"
    return (
        subject,
        _digest_text(tournaments, settings),
        _digest_html(tournaments, settings, today),
    )


def _digest_text(tournaments: list[Tournament], settings: Settings) -> str:
    lines = [settings.club_name, "Watched tournaments"]
    for tournament in tournaments:
        lines.append("")
        lines.append(tournament.name.upper())
        if tournament.venue:
            lines.append(tournament.venue)
        span = tournament.start_date.strftime("%b %-d")
        if tournament.end_date != tournament.start_date:
            span += f"–{tournament.end_date.strftime('%b %-d')}"
        lines.append(span)
        if data_as_of(tournament):
            lines.append(data_as_of(tournament))
        events = visible_events(tournament, settings)
        if not events:
            lines.append("Nobody signed up yet.")
            continue
        current_day = None
        for event in events:
            if event.day != current_day:
                current_day = event.day
                lines.append("")
                lines.append(day_label(event.day))
            clock = _clock(event)
            title = f"{clock}  {event.name}" if clock else event.name
            lines.append(title)
            for fencer in event.fencers:
                star = "★  " if is_our_club(fencer.club, settings) else "·  "
                place = _place(event, fencer)
                suffix = f"  ({place})" if place else ""
                lines.append(f"  {star}{fencer.name}{suffix}")
                lines.append(f"     {fencer.club}")
    return "\n".join(lines)


def _digest_html(
    tournaments: list[Tournament],
    settings: Settings,
    today: date,
) -> str:
    blocks: list[str] = []
    for tournament in tournaments:
        venue = (
            f'<div style="color:#94a3b8;font-size:13px;margin-top:2px;">{_escape(tournament.venue)}</div>'
            if tournament.venue
            else ""
        )
        span = tournament.start_date.strftime("%b %-d")
        if tournament.end_date != tournament.start_date:
            span += f"–{tournament.end_date.strftime('%b %-d')}"
        events = visible_events(tournament, settings)
        if not events:
            body = '<p style="margin:8px 0 0;color:#64748b;">Nobody signed up yet.</p>'
        else:
            body = _events_html(events, settings)
        blocks.append(
            '<div style="margin:20px 0 0;padding-top:16px;border-top:1px solid #e7e0cf;">'
            f'<div style="font-size:18px;color:#0a1628;font-weight:700;">{_escape(tournament.name)}</div>'
            f"{venue}"
            f'<div style="color:#8a6d14;font-size:13px;margin-top:2px;">{_escape(span)}</div>'
            + (f'<div style="color:#94a3b8;font-size:12px;margin-top:2px;">{_escape(data_as_of(tournament))}</div>'
               if data_as_of(tournament) else "")
            + f"{body}</div>"
        )
    return (
        "<div style=\"font-family:Georgia,'Times New Roman',serif;background:#f8fafc;padding:24px;\">"
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e7e0cf;'
        'border-radius:8px;overflow:hidden;">'
        '<div style="background:#0a1628;color:#d4af37;padding:18px 24px;">'
        f'<div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;">{_escape(settings.club_name)}</div>'
        '<div style="font-size:20px;color:#ffffff;margin-top:6px;line-height:1.3;">Watched tournaments</div>'
        f'<div style="color:#94a3b8;font-size:13px;margin-top:4px;">{_escape(today.strftime("%A, %B %-d"))}</div>'
        "</div>"
        f'<div style="padding:4px 24px 28px;">{"".join(blocks)}</div>'
        "</div></div>"
    )


def _events_html(events: list[Event], settings: Settings) -> str:
    blocks: list[str] = []
    current_day = None
    for event in events:
        if event.day != current_day:
            current_day = event.day
            blocks.append(
                '<p style="margin:16px 0 6px;font-size:11px;letter-spacing:.12em;'
                'color:#8a6d14;font-weight:700;text-transform:uppercase;">'
                f"{_escape(day_label(event.day))}</p>"
            )
        clock = _clock(event)
        clock_html = (
            f'<span style="color:#8a6d14;font-weight:600;letter-spacing:.04em;">{_escape(clock)}</span>'
            if clock
            else ""
        )
        people: list[str] = []
        for fencer in event.fencers:
            ours = is_our_club(fencer.club, settings)
            mark = (
                '<span style="color:#0f766e;font-weight:700;">★</span>'
                if ours
                else '<span style="color:#94a3b8;">·</span>'
            )
            name_style = "font-weight:600;color:#0a1628;" if ours else "font-weight:600;color:#1e293b;"
            place = _place(event, fencer)
            place_html = (
                f'<span style="color:#64748b;font-weight:500;"> · {_escape(place)}</span>' if place else ""
            )
            people.append(
                f'<tr><td style="padding:8px 0 2px;vertical-align:top;width:18px;">{mark}</td>'
                f'<td style="padding:8px 0 2px;">'
                f'<div style="{name_style}">{_escape(fencer.name)}{place_html}</div>'
                f'<div style="color:#64748b;font-size:13px;">{_escape(fencer.club)}</div>'
                "</td></tr>"
            )
        blocks.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 8px;">'
            '<tr><td style="padding:0 0 4px;font-size:16px;color:#0a1628;">'
            f'{clock_html}{"&nbsp;&nbsp;" if clock_html else ""}'
            f"<strong>{_escape(event.name)}</strong></td></tr>"
            '<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f"{''.join(people)}</table></td></tr></table>"
        )
    return "".join(blocks)


def send_daily_digest(
    settings: Settings,
    store: Store,
    now: datetime | None = None,
    force: bool = False,
) -> str | None:
    """Send today's snapshot. Returns the subject, or None when nothing went out.

    ``force`` is the on-demand button: it ignores the daily window and does not
    consume today's scheduled send. A scheduled send that fails to go out is not
    marked sent, so the next hourly tick retries it.

    Nothing is sent when no tournament is being watched. A watched tournament
    with nobody signed up is still included.
    """
    now = now or datetime.now()
    if not force and not digest_due(store, now):
        return None
    tournaments = watched_tournaments(store)
    if not tournaments:
        return None
    subject, body, html = build_daily_digest(tournaments, settings, now.date())
    sent = send_digest(settings, subject, body, digest_recipients_for(store), html=html)
    if sent is SKIPPED:
        return None
    if not force:
        store.set_setting(DIGEST_SENT_ON_KEY, now.date().isoformat())
    return subject


def tracked_count(tournament: Tournament, settings: Settings) -> int:
    return sum(1 for event in tournament.events for fencer in event.fencers if is_tracked(fencer, settings))
