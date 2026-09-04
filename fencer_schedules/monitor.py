from __future__ import annotations

import argparse
import json
import logging

from fencer_schedules.club import is_our_club
from fencer_schedules.config import DEFAULT_ALERT_RECIPIENT, Settings
from fencer_schedules.db import Store, Watch
from fencer_schedules.load import load_tournament
from fencer_schedules.models import Event, Tournament
from fencer_schedules.notify import send_digest

logger = logging.getLogger("fencer_schedules.monitor")


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


def run(settings: Settings, store: Store, dry_run: bool = False) -> list[str]:
    """Evaluate every watch; return the subjects of emails sent."""
    recipients = recipients_for(store)
    subjects: list[str] = []
    for watch in store.watches():
        tournament = store.get(watch.askfred_id)
        if tournament is None:
            if not dry_run:
                store.delete_watches(watch.askfred_id)
            continue
        try:
            fresh = load_tournament(watch.askfred_id, settings)
        except Exception:
            logger.exception("watch %s failed to load; skipping", watch.askfred_id)
            continue
        last_seen = json.loads(watch.last_seen or "{}")
        additions: list[tuple[Event, list[list[str]]]] = []
        snapshot: dict[str, list[list[str]]] = {}
        for event in _watched_events(watch, fresh):
            current = _names(event, watch, settings)
            key = event.source_event_id
            snapshot[key] = current
            if key in last_seen:
                new = new_names(last_seen[key], current)
                if new:
                    additions.append((event, new))
        if additions:
            subject, body = build_digest(fresh, additions, settings)
            if dry_run:
                logger.info("dry-run digest:\n%s\n%s", subject, body)
                print(subject)
                print(body)
                print()
            else:
                send_digest(settings, subject, body, recipients)
                subjects.append(subject)
        if not dry_run:
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
