import requests
import logging
import time
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from typing import Dict, List, Set

from ..crud import get_or_create_fencer, get_or_create_tournament, update_or_create_registration
from .notification_service import send_registration_notification
from .mailgun_client import NotificationError

# Constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds

logger = logging.getLogger(__name__)


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
    """Heuristically determine if a table contains tournament registrations."""
    header_labels = _extract_table_headers(table)

    if len(header_labels) < 3:
        return False

    def has_any(keywords: List[str]) -> bool:
        return any(any(keyword in label for keyword in keywords) for label in header_labels)

    has_name = has_any(["fencer", "name"])
    has_event = has_any(["event"])
    has_date = has_any(["date"])

    return has_name and has_event and has_date


def _should_skip_heading(tournament_name: str) -> bool:
    """Return True when the heading is metadata, not a tournament name."""
    normalized = tournament_name.strip()
    if not normalized:
        return True

    lower = normalized.lower()
    if lower in {"tournaments", "registrations", "club contacts"}:
        return True

    if normalized.startswith("(") and normalized.endswith(")"):
        return True

    return False


def normalize_club_url(url: str) -> str:
    """
    Normalize fencingtracker.com club URLs to registration page URLs.

    Accepts:
    - https://fencingtracker.com/club/123/Name
    - https://fencingtracker.com/club/123/Name/registrations

    Returns:
    - https://fencingtracker.com/club/123/Name/registrations

    Raises:
    - ValueError if URL doesn't match expected pattern

    Examples:
        >>> normalize_club_url("https://fencingtracker.com/club/100261977/Elite%20FC")
        'https://fencingtracker.com/club/100261977/Elite%20FC/registrations'
        >>> normalize_club_url("https://fencingtracker.com/club/100261977/Elite%20FC/registrations")
        'https://fencingtracker.com/club/100261977/Elite%20FC/registrations'
    """
    # Parse the URL
    parsed = urlparse(url)

    # Validate scheme
    if parsed.scheme != 'https':
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Expected 'https'")

    # Validate domain
    if parsed.netloc not in ['fencingtracker.com', 'www.fencingtracker.com']:
        raise ValueError(f"Invalid domain: {parsed.netloc}. Expected 'fencingtracker.com'")

    # Validate path contains /club/
    if '/club/' not in parsed.path:
        raise ValueError(f"Invalid URL path: {parsed.path}. Expected path containing '/club/'")

    # Remove trailing slash for consistent handling
    path = parsed.path.rstrip('/')

    # Check if already ends with /registrations
    if path.endswith('/registrations'):
        return url.rstrip('/')

    # Append /registrations
    normalized_url = f"{parsed.scheme}://{parsed.netloc}{path}/registrations"
    return normalized_url


def scrape_and_persist(db: Session, club_url: str) -> Dict[str, int]:
    """
    Scrape registration data from fencingtracker.com club URL and persist to database.

    Args:
        db: Database session
        club_url: URL to the fencing club's registration page or club home page

    Returns:
        Dictionary with counts of new, updated, and total registrations

    Raises:
        ValueError: If URL is invalid
        Exception: If fetching or parsing fails after all retries
    """
    # Normalize the URL
    try:
        normalized_url = normalize_club_url(club_url)
        logger.info(f"Normalized URL: {normalized_url}")
    except ValueError as e:
        logger.error(f"URL normalization failed: {e}")
        raise

    # HTTP headers to avoid bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Retry logic with exponential backoff
    session = requests.Session()
    response = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Fetching registrations from {normalized_url} (attempt {attempt + 1}/{MAX_RETRIES})")
            response = session.get(normalized_url, headers=headers, timeout=TIMEOUT_SECONDS)

            # Check status code before raising to handle 4xx vs 5xx differently
            if response.status_code >= 400:
                # Don't retry client errors (4xx)
                if 400 <= response.status_code < 500:
                    logger.error(f"HTTP client error {response.status_code}: {response.reason}")
                    raise Exception(f"HTTP {response.status_code} error for {normalized_url}: {response.reason}")

                # Retry server errors (5xx)
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed after {MAX_RETRIES} attempts: HTTP {response.status_code}")
                    raise Exception(f"Failed to fetch data after {MAX_RETRIES} attempts: HTTP {response.status_code} {response.reason}")

                delay = RETRY_DELAYS[attempt]
                logger.warning(f"HTTP error {response.status_code}, retrying in {delay}s...")
                time.sleep(delay)
                continue

            logger.info(f"Successfully fetched data (HTTP {response.status_code})")
            break  # Success

        except requests.exceptions.RequestException as e:
            # Retry on connection errors
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed after {MAX_RETRIES} attempts: {e}")
                raise Exception(f"Failed to fetch data after {MAX_RETRIES} attempts: {e}")

            delay = RETRY_DELAYS[attempt]
            logger.warning(f"Connection error: {e}, retrying in {delay}s...")
            time.sleep(delay)

    if not response:
        raise Exception(f"Failed to fetch data from {normalized_url}")

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all tournament headings (h3 tags)
    headings = soup.find_all('h3')

    if not headings:
        logger.error("No tournament headings (<h3>) found on the page")
        raise Exception("No tournament sections found on the page")

    logger.info(f"Found {len(headings)} tournament sections")

    new_count = 0
    updated_count = 0
    total_count = 0

    processed_headings: Set[str] = set()

    # Process each tournament section
    for heading_idx, heading in enumerate(headings, start=1):
        tournament_name = heading.get_text(strip=True)
        logger.info(f"Processing tournament {heading_idx}/{len(headings)}: {tournament_name}")

        if _should_skip_heading(tournament_name):
            logger.debug(f"  [{tournament_name}] Skipping non-tournament heading")
            continue

        normalized_heading = tournament_name.lower()
        if normalized_heading in processed_headings:
            logger.debug(f"  [{tournament_name}] Already processed heading, skipping duplicate")
            continue

        processed_headings.add(normalized_heading)

        # Find the next table after this heading
        table = heading.find_next('table')

        if not table:
            logger.warning(f"  [{tournament_name}] No table found for tournament, skipping")
            continue

        if not _is_registration_table(table):
            logger.debug(f"  [{tournament_name}] Skipping non-registration table for heading")
            continue

        # Parse rows in this tournament's table
        rows = table.find_all('tr')[1:]  # Skip header row
        logger.info(f"  [{tournament_name}] Found {len(rows)} registrations")

        for row_idx, row in enumerate(rows, start=1):
            cells = row.find_all('td')

            if len(cells) != 4:
                logger.warning(f"  [{tournament_name}] Skipping row {row_idx} with {len(cells)} columns (expected 4)")
                continue

            try:
                # Correct parsing for fencingtracker.com structure:
                # Column 0: Name (fencer)
                # Column 1: Event (e.g., "Junior Women's Epee") - stored in events field
                # Column 2: Status (usually empty)
                # Column 3: Date (tournament date)
                fencer_name = cells[0].get_text(strip=True)
                event_name = cells[1].get_text(strip=True)
                # Skip cells[2] (Status) - appears to be empty
                event_date = cells[3].get_text(strip=True)

                # Skip empty rows
                if not fencer_name or not event_name:
                    logger.debug(f"  [{tournament_name}] Skipping row {row_idx} with empty fencer or event name")
                    continue

                # Use empty string if date is missing
                if not event_date:
                    event_date = "TBD"
                    logger.warning(f"  [{tournament_name}] Missing date for row {row_idx}, using 'TBD'")

                # Get or create fencer and tournament
                # Use tournament_name from heading, not from table
                fencer = get_or_create_fencer(db, fencer_name)
                tournament = get_or_create_tournament(db, tournament_name, event_date)

                # Store event_name in the events field where it belongs
                registration, is_new = update_or_create_registration(
                    db,
                    fencer,
                    tournament,
                    event_name,
                    normalized_url,
                )

                if is_new:
                    new_count += 1
                    # Send notification for new registration
                    try:
                        send_registration_notification(fencer_name, tournament_name, event_name, normalized_url)
                        logger.info(f"  [{tournament_name}] Notification sent: {fencer_name} -> {event_name}")
                    except NotificationError as e:
                        logger.error(f"  [{tournament_name}] Failed to send notification for {fencer_name}: {e}")
                else:
                    updated_count += 1

                total_count += 1

            except Exception as e:
                # Log the error but continue processing other rows
                logger.error(f"  [{tournament_name}] Error processing row {row_idx}: {e}")
                continue

    db.commit()
    logger.info(f"Scraping complete. Total: {total_count}, New: {new_count}, Updated: {updated_count}")

    return {
        "new": new_count,
        "updated": updated_count,
        "total": total_count
    }
