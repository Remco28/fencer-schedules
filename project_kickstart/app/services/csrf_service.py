"""CSRF token generation and validation helpers."""

import secrets
from typing import Optional

from sqlalchemy.orm import Session

from .. import crud

_TOKEN_BYTES = 32


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_hex(_TOKEN_BYTES)


def validate_csrf_token(
    session_token: Optional[str],
    provided_csrf_token: Optional[str],
    db: Session,
) -> bool:
    """Validate the provided CSRF token against the stored session token."""
    if not session_token or not provided_csrf_token:
        return False

    session = crud.get_session(db, session_token)
    if not session or not session.csrf_token:
        return False

    return secrets.compare_digest(session.csrf_token, provided_csrf_token)


def get_csrf_token(db: Session, session_token: Optional[str]) -> Optional[str]:
    """Fetch the CSRF token for the given session."""
    if not session_token:
        return None

    session = crud.get_session(db, session_token)
    if not session:
        return None

    return session.csrf_token
