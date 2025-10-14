"""Daily digest email generation and scheduling."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, Iterable, List, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session

from app import crud
from app.database import SessionLocal
from app.models import Registration, TrackedClub, TrackedFencer, User

from .notification_service import send_registration_notification


logger = logging.getLogger(__name__)

DIGEST_LOOKBACK_HOURS = 24


def apply_weapon_filter(
    registrations: Iterable[Registration],
    weapon_filter: Optional[str],
) -> List[Registration]:
    """Filter registrations to those that match the configured weapons."""
    if not weapon_filter:
        return list(registrations)

    allowed = {
        weapon.strip().lower()
        for weapon in weapon_filter.split(",")
        if weapon and weapon.strip()
    }

    if not allowed:
        return list(registrations)

    filtered: List[Registration] = []
    for registration in registrations:
        events_lower = registration.events.lower()
        if any(weapon in events_lower for weapon in allowed):
            filtered.append(registration)

    return filtered


def _collect_club_sections(
    db: Session,
    tracked_clubs: List[TrackedClub],
    since: datetime,
) -> tuple[List[Dict[str, object]], set[int]]:
    """
    Collect club sections for digest.

    Returns:
        Tuple of (sections list, set of registration IDs seen in clubs)
    """
    sections: List[Dict[str, object]] = []
    seen_registration_ids: set[int] = set()

    for tracked in tracked_clubs:
        registrations = crud.get_registrations_by_club_url(db, tracked.club_url, since=since)
        filtered = apply_weapon_filter(registrations, tracked.weapon_filter)

        if not filtered:
            continue

        section_rows = []
        for registration in filtered:
            seen_registration_ids.add(registration.id)
            section_rows.append(
                {
                    "fencer_name": registration.fencer.name,
                    "events": registration.events,
                    "tournament_name": registration.tournament.name,
                    "club_url": tracked.club_url,
                }
            )

        sections.append(
            {
                "club_name": tracked.club_name or tracked.club_url,
                "club_url": tracked.club_url,
                "rows": section_rows,
            }
        )

    return sections, seen_registration_ids


def _collect_fencer_sections(
    db: Session,
    tracked_fencers: List[TrackedFencer],
    since: datetime,
    seen_registration_ids: set[int],
) -> List[Dict[str, object]]:
    """
    Collect fencer sections for digest, skipping registrations already in club sections.

    Args:
        db: Database session
        tracked_fencers: List of tracked fencers
        since: Only include registrations created after this timestamp
        seen_registration_ids: Set of registration IDs already included in club sections

    Returns:
        List of fencer sections for digest
    """
    sections: List[Dict[str, object]] = []

    for tracked_fencer in tracked_fencers:
        registrations = crud.get_registrations_for_fencer(db, tracked_fencer.fencer_id, since=since)
        filtered = apply_weapon_filter(registrations, tracked_fencer.weapon_filter)

        # Deduplicate: skip registrations already in club sections
        deduplicated = [reg for reg in filtered if reg.id not in seen_registration_ids]

        if not deduplicated:
            continue

        section_rows = []
        for registration in deduplicated:
            section_rows.append(
                {
                    "fencer_name": registration.fencer.name,
                    "events": registration.events,
                    "tournament_name": registration.tournament.name,
                    "fencer_id": tracked_fencer.fencer_id,
                }
            )

        sections.append(
            {
                "fencer_name": tracked_fencer.display_name or f"Fencer {tracked_fencer.fencer_id}",
                "fencer_id": tracked_fencer.fencer_id,
                "rows": section_rows,
            }
        )

    return sections


def format_digest_email(
    user: User,
    club_sections: List[Dict[str, object]],
    fencer_sections: List[Dict[str, object]],
) -> str:
    """Return a plain-text digest email body with club and fencer sections."""
    total_registrations = sum(len(section["rows"]) for section in club_sections) + sum(
        len(section["rows"]) for section in fencer_sections
    )

    lines = [
        f"Hi {user.username},",
        "",
        f"Here are {total_registrations} new registrations from the past 24 hours:",
        "",
    ]

    # Club sections
    if club_sections:
        lines.append("TRACKED CLUBS")
        lines.append("=" * 40)
        lines.append("")

        for section in club_sections:
            club_name = section["club_name"]
            lines.append(club_name)
            lines.append("-" * len(club_name))

            for row in section["rows"]:
                lines.append(
                    f"* {row['fencer_name']} - {row['events']} ({row['tournament_name']})"
                )

            lines.append(f"Club page: {section['club_url']}")
            lines.append("")

    # Fencer sections
    if fencer_sections:
        lines.append("TRACKED FENCERS")
        lines.append("=" * 40)
        lines.append("")

        for section in fencer_sections:
            fencer_name = section["fencer_name"]
            lines.append(fencer_name)
            lines.append("-" * len(fencer_name))

            for row in section["rows"]:
                lines.append(
                    f"* {row['events']} ({row['tournament_name']})"
                )

            lines.append("")

    lines.extend(
        [
            "Manage your tracking preferences:",
            "/clubs",  # Relative path; replace with production URL if needed
            "",
            "- The Fencing Tracker Team",
        ]
    )

    return "\n".join(lines)


def send_user_digest(db: Session, user: User) -> bool:
    """Generate and send a digest email for a single user.

    Returns True if an email was sent, otherwise False.
    """
    if not user.email:
        logger.info("User %s has no email address configured; skipping", user.id)
        return False

    # Get tracked clubs and fencers
    tracked_clubs = crud.get_tracked_clubs(db, user.id, active=True)
    tracked_fencers = crud.get_all_tracked_fencers_for_user(db, user.id, active_only=True)

    if not tracked_clubs and not tracked_fencers:
        logger.debug("User %s has no tracked clubs or fencers; skipping digest", user.id)
        return False

    since = datetime.now(UTC) - timedelta(hours=DIGEST_LOOKBACK_HOURS)

    # Collect club sections first (to build deduplication set)
    club_sections, seen_registration_ids = _collect_club_sections(db, tracked_clubs, since)

    # Collect fencer sections (with deduplication)
    fencer_sections = _collect_fencer_sections(db, tracked_fencers, since, seen_registration_ids)

    if not club_sections and not fencer_sections:
        logger.info("No new registrations for user %s; skipping digest", user.id)
        return False

    total_registrations = sum(len(s['rows']) for s in club_sections) + sum(
        len(s['rows']) for s in fencer_sections
    )

    subject = f"Daily fencing update ({total_registrations} new)"
    body = format_digest_email(user, club_sections, fencer_sections)

    send_registration_notification(
        fencer_name="",
        tournament_name="",
        events="",
        source_url="",
        recipients=[user.email],
        subject=subject,
        body=body,
    )

    logger.info(
        "Sent digest to user %s (%s) with %s new registrations (%s clubs, %s fencers)",
        user.id,
        user.email,
        total_registrations,
        len(club_sections),
        len(fencer_sections),
    )

    return True


def send_daily_digests() -> None:
    """Send digests to all active users."""
    session = SessionLocal()
    try:
        users = crud.get_active_users(session)
        for user in users:
            try:
                send_user_digest(session, user)
                session.expire_all()
            except Exception as exc:  # pragma: no cover - defensive logging
                session.rollback()
                logger.exception("Failed to send digest to user %s: %s", user.id, exc)
    finally:
        session.close()


def start_digest_scheduler() -> None:
    """Start the blocking APScheduler for digests."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        send_daily_digests,
        "cron",
        hour=9,
        minute=0,
        id="daily_digest",
    )

    logger.info("Daily digest scheduler started (9:00 AM)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover - CLI convenience
        logger.info("Digest scheduler stopped")
