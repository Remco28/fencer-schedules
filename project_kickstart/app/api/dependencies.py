"""Shared dependencies for API routes."""

import os
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import auth_service, csrf_service, rate_limit_service


SESSION_COOKIE_NAME = "session_token"
templates = Jinja2Templates(directory="app/templates")


def get_templates() -> Jinja2Templates:
    """Return the shared Jinja2 template environment."""
    return templates


def get_optional_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated user if a valid session is present."""
    request.state.session_token = session_token
    user = auth_service.validate_session(db, session_token)
    if user:
        request.state.user = user
        request.state.csrf_token = csrf_service.get_csrf_token(db, session_token)
    else:
        request.state.csrf_token = None
    return user


def get_current_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    """Require an authenticated user."""
    user = get_optional_user(request, session_token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require that the current user has admin privileges."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@pass_context
def csrf_token(context) -> str:
    """Expose the CSRF token to templates via a helper."""
    request = context.get("request")
    if not isinstance(request, Request):
        return ""

    token = getattr(request.state, "csrf_token", None)
    return token or ""


templates.env.globals["csrf_token"] = csrf_token


async def validate_csrf(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> None:
    """Validate CSRF token for state-changing requests."""
    content_type = request.headers.get("content-type", "").lower()

    provided_token: Optional[str]
    if content_type.startswith("application/json"):
        provided_token = request.headers.get("x-csrf-token")
    else:
        form = await request.form()
        provided_token = form.get("csrf_token") if form is not None else None

    if not csrf_service.validate_csrf_token(session_token, provided_token, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


async def check_login_rate_limit(request: Request) -> None:
    """Rate limit login attempts by username."""
    max_attempts = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5"))
    window_sec = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "300"))

    # Extract username from form or JSON
    content_type = request.headers.get("content-type", "").lower()
    username: Optional[str] = None

    if content_type.startswith("application/json"):
        body = await request.json()
        username = body.get("username")
    else:
        form = await request.form()
        username = form.get("username") if form is not None else None

    if not username:
        # If we can't extract username, use IP address as fallback
        username = request.client.host if request.client else "unknown"

    key = f"login:{username}"
    is_allowed, _ = rate_limit_service.check_rate_limit(key, max_attempts, window_sec)

    if not is_allowed:
        retry_after = rate_limit_service.get_retry_after(key, window_sec)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


async def check_register_rate_limit(request: Request) -> None:
    """Rate limit registration attempts by IP address."""
    max_attempts = int(os.getenv("REGISTER_RATE_LIMIT_ATTEMPTS", "3"))
    window_sec = int(os.getenv("REGISTER_RATE_LIMIT_WINDOW_SEC", "3600"))

    # Use IP address for registration rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Consider X-Forwarded-For if behind proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP from X-Forwarded-For chain
        client_ip = forwarded_for.split(",")[0].strip()

    key = f"register:{client_ip}"
    is_allowed, _ = rate_limit_service.check_rate_limit(key, max_attempts, window_sec)

    if not is_allowed:
        retry_after = rate_limit_service.get_retry_after(key, window_sec)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
