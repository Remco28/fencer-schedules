from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime

from fencer_schedules.club import is_our_club
from fencer_schedules.config import DEFAULT_ALERT_RECIPIENT, Settings
from fencer_schedules.db import Store, Watch
from fencer_schedules.load import load_tournament
from fencer_schedules.models import Event, Tournament
from fencer_schedules.notify import send_digest

logger = logging.getLogger("fencer_schedules.monitor")

ALERT_TIMES_KEY = "alert_times"
DEFAULT_ALERT_TIMES = ["09:00", "21:00"]
CHECK_WINDOW_MINUTES = 30

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_alert_times(raw: str | None) -> list[str]:
    """Parse comma-separated HH:MM values; drop blanks/invalid, dedupe, sort."""
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for part in raw.split(","):
        value = part.strip()
        if not value or not _TIME_RE.match(value):
            continue
        if value not in seen:
            seen.add(value)
            out.append(value)
    out.sort()
    return out


def normalize_alert_times(values: list[str] | str | None) -> str:
    """Normalize posted form values (or a raw string) to comma-separated HH:MM."""
    if values is None:
        return ""
    if isinstance(values, str):
        values = [values]
    # Each posted value may itself contain commas (single-field fallback).
    flat: list[str] = []
    for value in values:
        flat.extend((value or "").split(","))
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in flat:
        value = part.strip()
        if not value or not _TIME_RE.match(value):
            continue
        if value not in seen:
            seen.add(value)
            cleaned.append(value)
    cleaned.sort()
    return ",".join(cleaned)


def alert_times_for(store: Store) -> list[str]:
    """Saved HH:MM values, or the 09:00,21:00 default when unset/invalid."""
    parsed = parse_alert_times(store.get_setting(ALERT_TIMES_KEY, ""))
    return parsed if parsed else list(DEFAULT_ALERT_TIMES)


def is_check_hour(now: datetime, times: list[str]) -> bool:
    """True when ``now`` is within ±30 minutes of any HH:MM (midnight-aware)."""
    now_minutes = now.hour * 60 + now.minute
    for value in times:
        match = _TIME_RE.match(value.strip())
        if not match:
            continue
        target = int(match.group(1)) * 60 + int(match.group(2))
        diff = abs(now_minutes - target)
        diff = min(diff, 24 * 60 - diff)
        if diff <= CHECK_WINDOW_MINUTES:
            return True
    return False


def new_names(last_seen: list[list[str]], current: list[list[str]]) -> list[list[str]]:
    """Return (name, club) pairs in ``current`` but not ``last_seen``."""
    seen = {tuple(pair) for pair in last_seen}
    return [pair for pair in current if tuple(pair) not in seen]


def build_digest(
    tournament: Tournament,
    additions: list[tuple[Event, list[list[str]]]],
    settings: Settings,
) -> tuple[str, str]:
    total = sum(len(names) for _, names in additions)
    subject = f"New registrants: {tournament.name} ({total} new)"
    lines: list[str] = []
    for event, names in additions:
        header = event.day.strftime("%A, %B %-d")
        if event.clock:
            header += " · " + event.clock.strftime("%I:%M %p").lstrip("0")
        lines.append(f"{header} — {event.name}")
        for name, club in names:
            mark = " [CLUB]" if is_our_club(club, settings) else ""
            lines.append(f"  - {name} — {club}{mark}")
    return subject, "\n".join(lines)


def _watched_events(watch: Watch, tournament: Tournament) -> list[Event]:
    if watch.notify_kind == "all":
        event = next((e for e in tournament.events if e.source_event_id == watch.event_id), None)
        return [event] if event else []
    return [e for e in tournament.events if e.fencers]


def _names(event: Event, watch: Watch, settings: Settings) -> list[list[str]]:
    fencers = event.fencers
    if watch.notify_kind == "club":
        fencers = [f for f in fencers if is_our_club(f.club, settings)]
    return [[f.name, f.club] for f in fencers]


def recipients_for(store: Store) -> list[str]:
    raw = store.get_setting("alert_recipient", DEFAULT_ALERT_RECIPIENT)
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def run(
    settings: Settings,
    store: Store,
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[str]:
    """Evaluate every watch; return the subjects of emails sent."""
    if not dry_run:
        current = now or datetime.now()
        if not is_check_hour(current, alert_times_for(store)):
            logger.info("skipping watcher run at %s: not a check hour", current.strftime("%H:%M"))
            return []
    recipients = recipients_for(store)
    subjects: list[str] = []
    watches_by_tournament: dict[str, list[Watch]] = {}
    for watch in store.watches():
        watches_by_tournament.setdefault(watch.askfred_id, []).append(watch)

    for askfred_id, watches in watches_by_tournament.items():
        tournament = store.get(askfred_id)
        if tournament is None:
            if not dry_run:
                store.delete_watches(askfred_id)
            continue
        try:
            # Load once per tournament, even when multiple watch types overlap.
            fresh = load_tournament(askfred_id, settings)
        except Exception:
            logger.exception("watch %s failed to load; skipping", askfred_id)
            continue

        additions_by_event: dict[str, tuple[Event, list[list[str]]]] = {}
        snapshots: list[tuple[Watch, dict[str, list[list[str]]]]] = []
        for watch in watches:
            last_seen = json.loads(watch.last_seen or "{}")
            snapshot: dict[str, list[list[str]]] = {}
            for event in _watched_events(watch, fresh):
                current = _names(event, watch, settings)
                key = event.source_event_id
                snapshot[key] = current
                if key not in last_seen:
                    continue
                new = new_names(last_seen[key], current)
                if not new:
                    continue
                if key not in additions_by_event:
                    additions_by_event[key] = (event, [])
                combined = additions_by_event[key][1]
                for pair in new:
                    if pair not in combined:
                        combined.append(pair)
            snapshots.append((watch, snapshot))

        additions = list(additions_by_event.values())
        if additions:
            subject, body = build_digest(fresh, additions, settings)
            if dry_run:
                logger.info("dry-run digest:\n%s\n%s", subject, body)
                print(subject)
                print(body)
                print()
            else:
                # One email per tournament per run, not one per overlapping watch.
                send_digest(settings, subject, body, recipients)
                subjects.append(subject)

        # Only advance baselines after a successful send (or a no-change run).
        if not dry_run:
            for watch, snapshot in snapshots:
                store.save_last_seen(watch, snapshot)
    return subjects


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the registrant watcher once.")
    parser.add_argument("--dry-run", action="store_true", help="Print digests; never send or write.")
    parser.add_argument("--once", action="store_true", help="Run once (default; cron/systemd call it).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = Settings.load()
    store = Store(settings.database_path)
    subjects = run(settings, store, dry_run=args.dry_run)
    if args.dry_run:
        print(f"{len(subjects)} digest(s) would be sent (dry-run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
