"""Authentication and user management services."""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .. import crud
from ..models import User
from . import csrf_service
from .notification_service import send_registration_notification

try:  # pragma: no cover - executed when bcrypt is available
    import bcrypt  # type: ignore

    _HAS_BCRYPT = True
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without bcrypt
    _HAS_BCRYPT = False


SESSION_DURATION_DAYS = 30
SESSION_TOKEN_BYTES = 32


class AuthenticationError(Exception):
    """Raised when authentication fails."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    if not isinstance(password, str):
        raise TypeError("Password must be a string")

    password_bytes = password.encode("utf-8")
    if _HAS_BCRYPT:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, 390_000)
    return "pbkdf2$" + salt.hex() + "$" + derived.hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Validate a plaintext password against its hash."""
    if not password_hash:
        return False

    if password_hash.startswith("pbkdf2$"):
        try:
            _, salt_hex, derived_hex = password_hash.split("$")
        except ValueError:
            return False

        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(derived_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390_000)
        return secrets.compare_digest(candidate, expected)

    if not _HAS_BCRYPT:
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Raised when stored hash is invalid
        return False


def register_user(username: str, email: str, password: str, db: Session) -> User:
    """Register a new user account."""
    username = username.strip()
    email = email.strip()

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    existing = crud.get_user_by_username(db, username)
    if existing:
        raise ValueError("Username already exists")

    password_hash = hash_password(password)
    user = crud.create_user(db, username=username, email=email, password_hash=password_hash)

    try:
        notify_admin_new_user(user)
    except Exception:
        # Best effort notification; do not block registration
        pass

    return user


def authenticate(username: str, password: str, db: Session) -> Optional[User]:
    """Authenticate a user and return the user record on success."""
    user = crud.get_user_by_username(db, username.strip())

    if not user or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def generate_session_token() -> str:
    """Generate a random session token."""
    return secrets.token_hex(SESSION_TOKEN_BYTES)


def create_session(db: Session, user_id: int) -> Tuple[str, datetime]:
    """Create a new session for the given user."""
    expires_at = datetime.now(UTC) + timedelta(days=SESSION_DURATION_DAYS)
    token = generate_session_token()
    csrf_token = csrf_service.generate_csrf_token()
    crud.create_session(
        db,
        user_id=user_id,
        session_token=token,
        expires_at=expires_at,
        csrf_token=csrf_token,
    )
    return token, expires_at


def validate_session(db: Session, session_token: Optional[str]) -> Optional[User]:
    """Validate a session token and return the associated user if valid."""
    if not session_token:
        return None

    session = crud.get_session(db, session_token)
    if not session:
        return None

    # Handle both naive and aware datetimes for backwards compatibility
    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        # Convert naive datetime to UTC for comparison
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now:
        crud.delete_session(db, session_token)
        return None

    user = crud.get_user_by_id(db, session.user_id)
    if not user or not user.is_active:
        return None

    return user


def logout(db: Session, session_token: Optional[str]) -> None:
    """Invalidate a session token."""
    if session_token:
        crud.delete_session(db, session_token)


def notify_admin_new_user(user: User) -> None:
    """Send an email notification to the system admin about a new user signup."""
    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        defaults = os.getenv("MAILGUN_DEFAULT_RECIPIENTS", "")
        admin_email = defaults.split(",")[0].strip() if defaults else ""

    if not admin_email:
        return

    subject = f"New user signup: {user.username}"
    body = (
        "A new user has signed up for the fencing registration tracker.\n\n"
        f"Username: {user.username}\n"
        f"Email: {user.email}\n"
        f"Signup Date: {user.created_at}\n"
    )

    send_registration_notification(
        fencer_name="",
        tournament_name="",
        events="",
        source_url="",
        recipients=[admin_email],
        subject=subject,
        body=body,
    )
