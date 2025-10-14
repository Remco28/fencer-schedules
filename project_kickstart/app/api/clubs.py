"""Routes for managing tracked clubs."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import TrackedClub, User
from app.services.club_validation_service import validate_club_url

from .dependencies import get_current_user, templates, validate_csrf


router = APIRouter()

ALLOWED_WEAPONS = ["foil", "epee", "saber"]


def _normalize_weapon_filter(raw_values: Optional[Any]) -> Optional[str]:
    if not raw_values:
        return None

    if isinstance(raw_values, str):
        values = [raw_values]
    elif isinstance(raw_values, (list, tuple, set)):
        values = list(raw_values)
    else:
        return None

    normalized = []
    for value in values:
        if value is None:
            continue
        lowered = value.lower()
        if lowered in ("all", "any"):
            return None
        if lowered in ALLOWED_WEAPONS and lowered not in normalized:
            normalized.append(lowered)

    if not normalized or len(normalized) == len(ALLOWED_WEAPONS):
        return None

    ordered = [weapon for weapon in ALLOWED_WEAPONS if weapon in normalized]
    return ",".join(ordered)


def _serialize_tracked_club(tracked: TrackedClub) -> Dict[str, Any]:
    return {
        "id": tracked.id,
        "club_url": tracked.club_url,
        "club_name": tracked.club_name,
        "weapon_filter": tracked.weapon_filter,
        "active": tracked.active,
        "created_at": tracked.created_at.isoformat() if tracked.created_at else None,
    }


def _build_club_context(db: Session, user: User, error: Optional[str] = None) -> Dict[str, Any]:
    tracked = crud.get_tracked_clubs(db, user.id, active=None)
    active_clubs = [club for club in tracked if club.active]
    inactive_clubs = [club for club in tracked if not club.active]

    context: Dict[str, Any] = {
        "tracked_clubs": tracked,
        "active_clubs": active_clubs,
        "inactive_clubs": inactive_clubs,
        "weapon_options": ALLOWED_WEAPONS,
    }

    if error:
        context["error"] = error

    return context


@router.get("/clubs", response_class=HTMLResponse)
def list_tracked_clubs(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "tracked_clubs.html",
        {
            "request": request,
            "user": user,
            **_build_club_context(db, user),
        },
    )


@router.post("/clubs/add")
async def add_tracked_club(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = await request.json()
        weapon_filter_raw = payload.get("weapon_filter")
        club_url = (payload.get("club_url") or "").strip()
        provided_name = (payload.get("club_name") or "").strip()
    else:
        form = await request.form()
        club_url = (form.get("club_url") or "").strip()
        provided_name = (form.get("club_name") or "").strip()
        weapon_filter_raw = form.getlist("weapon_filter")

    if not club_url:
        message = "Club URL is required"
        if content_type.startswith("application/json"):
            return JSONResponse({"detail": message}, status_code=status.HTTP_400_BAD_REQUEST)
        return templates.TemplateResponse(
            "tracked_clubs.html",
            {
                "request": request,
                "user": user,
                **_build_club_context(db, user, error=message),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        normalized_url, detected_name = validate_club_url(club_url)
    except ValueError as exc:
        message = str(exc)
        if content_type.startswith("application/json"):
            return JSONResponse({"detail": message}, status_code=status.HTTP_400_BAD_REQUEST)
        return templates.TemplateResponse(
            "tracked_clubs.html",
            {
                "request": request,
                "user": user,
                **_build_club_context(db, user, error=message),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    weapon_filter = _normalize_weapon_filter(weapon_filter_raw)
    club_name = provided_name or detected_name

    existing = crud.get_tracked_club_by_user_and_url(db, user.id, normalized_url)

    if existing:
        if not existing.active:
            crud.update_tracked_club(
                db,
                existing.id,
                active=True,
                weapon_filter=weapon_filter,
                club_name=club_name,
            )
            db.commit()
            db.refresh(existing)
            tracked = existing
        else:
            message = "Club already tracked"
            if content_type.startswith("application/json"):
                return JSONResponse({"detail": message}, status_code=status.HTTP_400_BAD_REQUEST)
            return templates.TemplateResponse(
                "tracked_clubs.html",
                {
                    "request": request,
                    "user": user,
                    **_build_club_context(db, user, error=message),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        try:
            tracked = crud.create_tracked_club(
                db,
                user_id=user.id,
                club_url=normalized_url,
                club_name=club_name,
                weapon_filter=weapon_filter,
            )
            db.commit()
            db.refresh(tracked)
        except IntegrityError:
            db.rollback()
            message = "Club already tracked"
            if content_type.startswith("application/json"):
                return JSONResponse({"detail": message}, status_code=status.HTTP_400_BAD_REQUEST)
            return templates.TemplateResponse(
                "tracked_clubs.html",
                {
                    "request": request,
                    "user": user,
                    **_build_club_context(db, user, error=message),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    if content_type.startswith("application/json"):
        return JSONResponse(_serialize_tracked_club(tracked), status_code=status.HTTP_201_CREATED)

    return RedirectResponse(url="/clubs", status_code=status.HTTP_303_SEE_OTHER)


@router.patch("/clubs/{tracked_club_id}")
async def update_tracked_club(
    tracked_club_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    tracked = crud.get_tracked_club_for_user(db, tracked_club_id, user.id)
    if not tracked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked club not found")

    payload = await request.json()
    weapon_filter = _normalize_weapon_filter(payload.get("weapon_filter"))
    club_name = (payload.get("club_name") or "").strip() or None
    active = payload.get("active")

    updates: Dict[str, Any] = {}
    if weapon_filter is not None or payload.get("weapon_filter") == []:
        updates["weapon_filter"] = weapon_filter
    if club_name is not None:
        updates["club_name"] = club_name
    if isinstance(active, bool):
        updates["active"] = active

    if not updates:
        return JSONResponse(_serialize_tracked_club(tracked))

    crud.update_tracked_club(db, tracked.id, **updates)
    db.commit()

    db.refresh(tracked)
    return JSONResponse(_serialize_tracked_club(tracked))


@router.delete("/clubs/{tracked_club_id}")
def remove_tracked_club(
    tracked_club_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    tracked = crud.get_tracked_club_for_user(db, tracked_club_id, user.id)
    if not tracked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked club not found")

    crud.deactivate_tracked_club(db, tracked_club_id)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
