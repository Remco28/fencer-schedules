"""Fencer profile scraper service with throttling and error handling."""

import hashlib
import os
import random
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import UTC, datetime
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from ..crud import (
    get_fencer_by_fencingtracker_id,
    get_or_create_fencer,
    get_or_create_tournament,
    update_or_create_registration,
    get_all_active_tracked_fencers,
    update_fencer_check_status,
)
from ..models import Registration
from .fencer_validation_service import build_fencer_profile_url

# Environment configuration with defaults
FENCER_SCRAPE_ENABLED = os.getenv("FENCER_SCRAPE_ENABLED", "true").lower() == "true"
FENCER_SCRAPE_DELAY_SEC = float(os.getenv("FENCER_SCRAPE_DELAY_SEC", "5"))
FENCER_SCRAPE_JITTER_SEC = float(os.getenv("FENCER_SCRAPE_JITTER_SEC", "2"))
FENCER_MAX_FAILURES = int(os.getenv("FENCER_MAX_FAILURES", "3"))
FENCER_FAILURE_COOLDOWN_MIN = int(os.getenv("FENCER_FAILURE_COOLDOWN_MIN", "60"))

# HTTP constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds

logger = logging.getLogger(__name__)

PROFILE_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _should_skip_fencer(tracked_fencer) -> bool:
    """
    Determine if a tracked fencer should be skipped due to recent failures.

    Returns True if fencer has hit failure threshold and cooldown hasn't expired.
    """
    if tracked_fencer.failure_count < FENCER_MAX_FAILURES:
        return False

    if not tracked_fencer.last_failure_at:
        return False

    # Check if cooldown period has expired
    cooldown_seconds = FENCER_FAILURE_COOLDOWN_MIN * 60
    time_since_failure = (datetime.now(UTC) - tracked_fencer.last_failure_at).total_seconds()

    if time_since_failure < cooldown_seconds:
        logger.debug(
            f"Skipping fencer {tracked_fencer.fencer_id} "
            f"(failures: {tracked_fencer.failure_count}, "
            f"cooldown: {int(cooldown_seconds - time_since_failure)}s remaining)"
        )
        return True

    return False


def _apply_delay_with_jitter():
    """Apply base delay with random jitter to spread out requests."""
    jitter = random.uniform(-FENCER_SCRAPE_JITTER_SEC, FENCER_SCRAPE_JITTER_SEC)
    delay = max(0, FENCER_SCRAPE_DELAY_SEC + jitter)
    logger.debug(f"Applying delay: {delay:.2f}s (base: {FENCER_SCRAPE_DELAY_SEC}s, jitter: {jitter:+.2f}s)")
    time.sleep(delay)


def _extract_table_headers(table) -> List[str]:
    """Return normalized header labels for the given table."""
    header_labels: List[str] = []

    thead = table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            header_labels = [cell.get_text(strip=True).lower() for cell in header_row.find_all(['th', 'td'])]

    if not header_labels:
        first_row = table.find('tr')
        if first_row:
            header_labels = [cell.get_text(strip=True).lower() for cell in first_row.find_all(['th', 'td'])]

    return [label for label in header_labels if label]


def _is_registration_table(table) -> bool:
    """Heuristically determine if a table contains fencer registrations."""
    header_labels = _extract_table_headers(table)

    if len(header_labels) < 3:
        return False

    def has_any(keywords: List[str]) -> bool:
        return any(any(keyword in label for keyword in keywords) for label in header_labels)

    has_event_or_tournament = has_any(["event", "tournament"])
    has_date = has_any(["date"])

    # Exclude results tables (they have "place" or "rating" columns)
    has_results_columns = has_any(["place", "rating", "earned", "class"])

    return has_event_or_tournament and has_date and not has_results_columns


def _compute_registration_hash(tables: List) -> str:
    """
    Compute a hash of registration table contents for change detection.

    This creates a stable hash based on the visible text content of all
    registration tables, which changes when registrations are added/removed.
    """
    content_parts = []

    for table in tables:
        if not _is_registration_table(table):
            continue

        # Extract all text content from registration rows
        rows = table.find_all('tr')[1:]  # Skip header
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:
                # Use tournament, event, date as stable identifiers
                row_text = '|'.join(cell.get_text(strip=True) for cell in cells[:3])
                content_parts.append(row_text)

    # Sort to ensure consistent ordering
    content_parts.sort()
    combined = '\n'.join(content_parts)

    # Return SHA256 hash
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def _extract_fencer_name_from_page(soup: BeautifulSoup, fencer_id: str) -> Optional[str]:
    """
    Attempt to extract the fencer's actual name from their profile page.

    Returns None if name cannot be determined.
    """
    # Look for common patterns in fencer profile pages
    # This is heuristic and may need adjustment based on actual page structure

    # Try h1 tag (common for page titles)
    h1 = soup.find('h1')
    if h1:
        name = h1.get_text(strip=True)
        if name and name.lower() not in ['profile', 'fencer', 'athlete']:
            return name

    # Try title tag
    title = soup.find('title')
    if title:
        title_text = title.get_text(strip=True)
        # Remove common suffixes like " - FencingTracker"
        if ' - ' in title_text:
            name = title_text.split(' - ')[0].strip()
            if name and name.lower() not in ['profile', 'fencer', 'athlete']:
                return name

    return None


def scrape_fencer_profile(
    db: Session,
    fencer_id: str,
    display_name: str = None,
    cached_hash: Optional[str] = None,
) -> Dict[str, any]:
    """
    Scrape a single fencer profile page and persist registrations.

    Args:
        db: Database session
        fencer_id: Fencingtracker numeric fencer ID
        display_name: Optional display name for logging
        cached_hash: Previous registration hash for change detection

    Returns:
        Dictionary with:
        - new: count of new registrations
        - updated: count of updated registrations
        - total: total registrations processed
        - hash: current registration hash
        - skipped: True if page unchanged

    Raises:
        Exception: If fetching or parsing fails after all retries
    """
    profile_url = build_fencer_profile_url(fencer_id, display_name)
    log_name = display_name or f"ID:{fencer_id}"

    logger.info(f"[{log_name}] Fetching fencer profile: {profile_url}")

    # Retry logic with exponential backoff
    session = requests.Session()
    response = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"[{log_name}] Fetching profile (attempt {attempt + 1}/{MAX_RETRIES})")
            response = session.get(
                profile_url,
                headers=PROFILE_REQUEST_HEADERS,
                timeout=TIMEOUT_SECONDS,
            )

            # Check status code before raising
            if response.status_code >= 400:
                # Don't retry client errors (4xx)
                if 400 <= response.status_code < 500:
                    logger.error(f"[{log_name}] HTTP {response.status_code}: {response.reason}")
                    raise Exception(f"HTTP {response.status_code} error for {profile_url}")

                # Retry server errors (5xx) and rate limits (429)
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"[{log_name}] Failed after {MAX_RETRIES} attempts: HTTP {response.status_code}")
                    raise Exception(f"Failed to fetch after {MAX_RETRIES} attempts: HTTP {response.status_code}")

                delay = RETRY_DELAYS[attempt]
                logger.warning(f"[{log_name}] HTTP {response.status_code}, retrying in {delay}s...")
                time.sleep(delay)
                continue

            logger.debug(f"[{log_name}] Successfully fetched profile (HTTP {response.status_code})")
            break  # Success

        except requests.exceptions.RequestException as e:
            # Retry on connection errors
            if attempt == MAX_RETRIES - 1:
                logger.error(f"[{log_name}] Failed after {MAX_RETRIES} attempts: {e}")
                raise Exception(f"Failed to fetch after {MAX_RETRIES} attempts: {e}")

            delay = RETRY_DELAYS[attempt]
            logger.warning(f"[{log_name}] Connection error: {e}, retrying in {delay}s...")
            time.sleep(delay)

    if not response:
        raise Exception(f"Failed to fetch profile from {profile_url}")

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find registration tables on fencer profile
    tables = soup.find_all('table')

    if not tables:
        logger.warning(f"[{log_name}] No tables found on profile page")
        current_hash = hashlib.sha256(b'').hexdigest()  # Empty hash
        return {
            "new": 0,
            "updated": 0,
            "total": 0,
            "hash": current_hash,
            "skipped": False,
        }

    # Compute hash of current page content for change detection
    current_hash = _compute_registration_hash(tables)

    # Check if page has changed since last scrape
    if cached_hash and current_hash == cached_hash:
        logger.info(f"[{log_name}] No changes detected (hash match), skipping parse")
        return {
            "new": 0,
            "updated": 0,
            "total": 0,
            "hash": current_hash,
            "skipped": True,
        }

    # Extract fencer's actual name from page if possible
    fencer_name_from_page = _extract_fencer_name_from_page(soup, fencer_id)

    new_count = 0
    updated_count = 0
    total_count = 0

    # Process each table that looks like a registration table
    for table_idx, table in enumerate(tables, start=1):
        if not _is_registration_table(table):
            logger.debug(f"[{log_name}] Skipping non-registration table {table_idx}")
            continue

        logger.debug(f"[{log_name}] Processing registration table {table_idx}")

        # Parse rows
        rows = table.find_all('tr')[1:]  # Skip header row
        logger.info(f"[{log_name}] Found {len(rows)} registrations in table {table_idx}")

        for row_idx, row in enumerate(rows, start=1):
            cells = row.find_all('td')

            if len(cells) < 3:
                logger.debug(f"[{log_name}] Skipping row {row_idx} with {len(cells)} columns (expected >=3)")
                continue

            try:
                # Fencer profile page structure (assumed similar to club page):
                # Column 0: Tournament name
                # Column 1: Event name
                # Column 2: Date
                tournament_name = cells[0].get_text(strip=True)
                event_name = cells[1].get_text(strip=True)
                event_date = cells[2].get_text(strip=True) if len(cells) > 2 else "TBD"

                # Skip empty rows
                if not tournament_name or not event_name:
                    logger.debug(f"[{log_name}] Skipping row {row_idx} with empty tournament or event")
                    continue

                # CRITICAL FIX: Look up fencer by fencingtracker_id first to avoid duplicates
                fencer = get_fencer_by_fencingtracker_id(db, fencer_id)

                if not fencer:
                    # Fencer doesn't exist yet - determine name and create
                    fencer_name = (
                        fencer_name_from_page
                        or display_name
                        or f"Fencer_{fencer_id}"  # Fallback only if we can't determine name
                    )

                    fencer = get_or_create_fencer(db, fencer_name)
                    fencer.fencingtracker_id = fencer_id
                    db.flush()
                    logger.debug(f"[{log_name}] Created new fencer record: {fencer_name}")
                else:
                    # Fencer exists - update name if we have a better one
                    if fencer_name_from_page and fencer.name.startswith("Fencer_"):
                        logger.info(f"[{log_name}] Updating fencer name from '{fencer.name}' to '{fencer_name_from_page}'")
                        fencer.name = fencer_name_from_page
                        db.flush()

                tournament = get_or_create_tournament(db, tournament_name, event_date)

                existing_registration = (
                    db.query(Registration)
                    .filter(
                        Registration.fencer_id == fencer.id,
                        Registration.tournament_id == tournament.id,
                    )
                    .one_or_none()
                )

                source_url = (
                    existing_registration.club_url
                    if existing_registration and existing_registration.club_url
                    else profile_url
                )

                registration, is_new = update_or_create_registration(
                    db,
                    fencer,
                    tournament,
                    event_name,
                    source_url,
                )

                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

                total_count += 1

            except Exception as e:
                logger.error(f"[{log_name}] Error processing row {row_idx}: {e}")
                continue

    logger.info(f"[{log_name}] Scraping complete. Total: {total_count}, New: {new_count}, Updated: {updated_count}")

    return {
        "new": new_count,
        "updated": updated_count,
        "total": total_count,
        "hash": current_hash,
        "skipped": False,
    }


def scrape_all_tracked_fencers(db: Session) -> Dict[str, any]:
    """
    Scrape all active tracked fencers with throttling and error handling.

    Returns:
        Summary statistics for the scraping run
    """
    if not FENCER_SCRAPE_ENABLED:
        logger.info("Fencer scraping is disabled (FENCER_SCRAPE_ENABLED=false)")
        return {
            "enabled": False,
            "fencers_scraped": 0,
            "fencers_skipped": 0,
            "fencers_failed": 0,
            "total_registrations": 0,
        }

    logger.info("Starting tracked fencer scraping run")

    # Get all active tracked fencers
    tracked_fencers = get_all_active_tracked_fencers(db)
    logger.info(f"Found {len(tracked_fencers)} active tracked fencers")

    if not tracked_fencers:
        logger.info("No tracked fencers to scrape")
        return {
            "enabled": True,
            "fencers_scraped": 0,
            "fencers_skipped": 0,
            "fencers_failed": 0,
            "total_registrations": 0,
        }

    scraped_count = 0
    skipped_count = 0
    failed_count = 0
    total_registrations = 0

    for idx, tracked_fencer in enumerate(tracked_fencers, start=1):
        logger.info(f"Processing fencer {idx}/{len(tracked_fencers)}: {tracked_fencer.display_name or tracked_fencer.fencer_id}")

        # Check if fencer should be skipped due to failures
        if _should_skip_fencer(tracked_fencer):
            skipped_count += 1
            continue

        # Apply delay with jitter (except for first fencer)
        if idx > 1:
            _apply_delay_with_jitter()

        # Scrape the fencer profile
        try:
            result = scrape_fencer_profile(
                db,
                tracked_fencer.fencer_id,
                tracked_fencer.display_name,
                cached_hash=tracked_fencer.last_registration_hash,
            )

            # Update check status (success) and cache hash
            update_fencer_check_status(db, tracked_fencer, datetime.now(UTC), success=True)
            tracked_fencer.last_registration_hash = result["hash"]
            db.commit()

            scraped_count += 1
            total_registrations += result["total"]

            if result["skipped"]:
                logger.info(
                    f"Scraped {tracked_fencer.display_name or tracked_fencer.fencer_id}: "
                    f"No changes detected (cached)"
                )
            else:
                logger.info(
                    f"Successfully scraped {tracked_fencer.display_name or tracked_fencer.fencer_id}: "
                    f"{result['total']} registrations ({result['new']} new, {result['updated']} updated)"
                )

        except Exception as e:
            # Update check status (failure)
            update_fencer_check_status(db, tracked_fencer, datetime.now(UTC), success=False)
            db.commit()

            failed_count += 1
            logger.error(
                f"Failed to scrape {tracked_fencer.display_name or tracked_fencer.fencer_id}: {e} "
                f"(failure count: {tracked_fencer.failure_count})"
            )

    logger.info(
        f"Fencer scraping run complete. "
        f"Scraped: {scraped_count}, Skipped: {skipped_count}, Failed: {failed_count}, "
        f"Total registrations: {total_registrations}"
    )

    return {
        "enabled": True,
        "fencers_scraped": scraped_count,
        "fencers_skipped": skipped_count,
        "fencers_failed": failed_count,
        "total_registrations": total_registrations,
    }


def fetch_fencer_display_name(fencer_id: str, timeout: float = 3.0) -> Optional[str]:
    """Fetch a fencer profile and attempt to extract the display name.

    Note: This function attempts to fetch without a slug, which may fail.
    It's used as a fallback when no display name is available yet.
    """
    # Try without slug first (may 404, that's expected)
    profile_url = build_fencer_profile_url(fencer_id, None)

    try:
        response = requests.get(
            profile_url,
            headers=PROFILE_REQUEST_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - observed via logging
        logger.debug("Auto-name fetch failed for fencer %s: %s", fencer_id, exc)
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    name = _extract_fencer_name_from_page(soup, fencer_id)
    if name:
        return name

    logger.debug("Auto-name extraction yielded no result for fencer %s", fencer_id)
    return None
