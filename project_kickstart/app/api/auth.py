"""Authentication routes."""

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import auth_service, rate_limit_service

from .dependencies import (
    SESSION_COOKIE_NAME,
    check_login_rate_limit,
    check_register_rate_limit,
    get_current_user,
    get_optional_user,
    validate_csrf,
    templates,
)


router = APIRouter()

COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
COOKIE_MAX_AGE = auth_service.SESSION_DURATION_DAYS * 24 * 60 * 60


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME)


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
):
    return templates.TemplateResponse("register.html", {"request": request, "user": user})


@router.post("/auth/register")
async def register_user(
    request: Request,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_register_rate_limit),
) -> Response:
    payload: Dict[str, Any]
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = await request.json()
    else:
        form = await request.form()
        payload = {key: form.get(key) for key in ("username", "email", "password")}

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not username or not email or not password:
        error_msg = "All fields are required"
        if content_type.startswith("application/json"):
            return JSONResponse({"detail": error_msg}, status_code=status.HTTP_400_BAD_REQUEST)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "user": None,
                "error": error_msg,
                "values": {"username": username, "email": email},
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = auth_service.register_user(username, email, password, db)
        db.commit()
    except ValueError as exc:
        db.rollback()
        error_msg = str(exc)
        if content_type.startswith("application/json"):
            return JSONResponse({"detail": error_msg}, status_code=status.HTTP_400_BAD_REQUEST)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "user": None,
                "error": error_msg,
                "values": {"username": username, "email": email},
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        db.rollback()
        if content_type.startswith("application/json"):
            raise
        raise

    if content_type.startswith("application/json"):
        return JSONResponse({"id": user.id, "username": user.username, "email": user.email}, status_code=status.HTTP_201_CREATED)

    response = RedirectResponse(url="/login?registered=1", status_code=status.HTTP_303_SEE_OTHER)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    context = {"request": request, "user": None}
    if request.query_params.get("registered"):
        context["message"] = "Account created successfully. Please log in."
    return templates.TemplateResponse("login.html", context)


@router.post("/auth/login")
async def login_user(
    request: Request,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_login_rate_limit),
) -> Response:
    payload: Dict[str, Any]
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = await request.json()
    else:
        form = await request.form()
        payload = {key: form.get(key) for key in ("username", "password")}

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    user = auth_service.authenticate(username, password, db)
    if not user:
        error_msg = "Invalid credentials"
        if content_type.startswith("application/json"):
            return JSONResponse({"detail": error_msg}, status_code=status.HTTP_401_UNAUTHORIZED)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "user": None,
                "error": error_msg,
                "values": {"username": username},
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Reset rate limit on successful login
    rate_limit_service.reset_rate_limit(f"login:{username}")

    token, _ = auth_service.create_session(db, user.id)
    db.commit()

    if content_type.startswith("application/json"):
        response = JSONResponse({"message": "ok"})
    else:
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    _set_session_cookie(response, token)
    return response


@router.post("/auth/logout")
def logout_user(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    _csrf: None = Depends(validate_csrf),
) -> Response:
    auth_service.logout(db, session_token)
    db.commit()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    _clear_session_cookie(response)
    return response


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse({"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin})
