from __future__ import annotations

import logging

from fencer_schedules.config import Settings

logger = logging.getLogger("fencer_schedules.notify")

# Returned when nothing was sent (dry-run, AgentMail unconfigured, no
# recipients). Callers must not treat that as delivery: the watcher keeps its
# baseline so the digest is reported again once email is configured.
SKIPPED = object()


def send_digest(
    settings: Settings,
    subject: str,
    body: str,
    recipients: list[str],
    send: bool = True,
    html: str | None = None,
) -> object:
    """Send one digest email through the AgentMail SDK.

    ``send=False`` is the dry-run guard — it never touches the network. The
    ``agentmail`` import is lazy so tests and dry-runs don't require the SDK.
    Returns ``SKIPPED`` when no email went out, otherwise a truthy marker.
    """
    if not send:
        logger.info("dry-run: not sending email (subject=%r)", subject)
        return SKIPPED
    if not settings.agentmail_api_key or not settings.agentmail_inbox:
        logger.warning("AgentMail not configured (missing API key/inbox); digest not sent")
        return SKIPPED
    to = [addr.strip() for addr in recipients if addr and addr.strip()]
    if not to:
        logger.warning("No recipients configured; digest not sent")
        return SKIPPED

    import agentmail  # lazy import (test seam: monkeypatch agentmail.AgentMail)

    client = agentmail.AgentMail(api_key=settings.agentmail_api_key)
    inbox_id = _resolve_inbox_id(client, settings.agentmail_inbox)
    kwargs: dict = {"to": to, "subject": subject, "text": body}
    if html:
        kwargs["html"] = html
    result = client.inboxes.messages.send(inbox_id, **kwargs)
    if not getattr(result, "message_id", None):
        raise RuntimeError("AgentMail did not return a message ID")
    logger.info("sent digest %r to %s", subject, ", ".join(to))
    return True


def _resolve_inbox_id(client, configured: str) -> str:
    """Map a configured inbox id/address to the id the send API wants."""
    inboxes = client.inboxes.list().inboxes
    for inbox in inboxes:
        inbox_id = getattr(inbox, "inbox_id", None)
        address = getattr(inbox, "address", None) or getattr(inbox, "email", None)
        if configured in {inbox_id, address} and inbox_id:
            return inbox_id
    raise RuntimeError("Configured AgentMail inbox was not returned by the API")
