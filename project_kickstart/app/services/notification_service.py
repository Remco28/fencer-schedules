import logging
from typing import Optional, List
from .mailgun_client import MailgunEmailClient, NotificationError


# Module-level client for lazy instantiation
_client: Optional[MailgunEmailClient] = None


def get_client() -> MailgunEmailClient:
    """Get or create the Mailgun client instance."""
    global _client
    if _client is None:
        _client = MailgunEmailClient()
    return _client


def send_registration_notification(
    fencer_name: str,
    tournament_name: str,
    events: str,
    source_url: str,
    recipients: Optional[List[str]] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
) -> str:
    """
    Send email notification for a new fencing registration.

    Args:
        fencer_name: Name of the fencer who registered
        tournament_name: Name of the tournament
        events: Events the fencer registered for
        source_url: URL where the registration was found
        recipients: Optional override for default recipients

    Returns:
        Mailgun message ID on success

    Raises:
        NotificationError: When sending fails after retries
    """
    client = get_client()

    if subject is not None and body is not None:
        return client.send_text(subject, body, to=recipients)

    default_subject = f"New fencing registration: {fencer_name}"
    message_body = (
        f"Fencer: {fencer_name}\n"
        f"Tournament: {tournament_name}\n"
        f"Events: {events}\n"
        f"Source: {source_url}"
    )

    return client.send_text(default_subject, message_body, to=recipients)


# Legacy function for backward compatibility
def send_notification(subject: str, body: str) -> None:
    """
    Legacy function for sending notifications (deprecated).
    Use send_registration_notification for new code.

    Args:
        subject: Email subject line
        body: Email body content (plain text)
    """
    logger = logging.getLogger(__name__)

    try:
        client = get_client()
        client.send_text(subject, body)
        logger.info(f"Email sent successfully: {subject}")
    except NotificationError as e:
        logger.error(f"Failed to send email: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        raise
