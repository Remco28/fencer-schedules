"""Routes for managing tracked fencers."""

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import TrackedFencer, User
from app.services import fencer_validation_service, fencer_scraper_service
from app.services.fencer_validation_service import build_fencer_profile_url

from .dependencies import get_current_user, templates, validate_csrf


router = APIRouter()

ALLOWED_WEAPONS = ["foil", "epee", "saber"]


class FencerStatus:
    __slots__ = ("label", "css", "description")

    def __init__(self, label: str, css: str, description: Optional[str]):
        self.label = label
        self.css = css
        self.description = description


def _determine_status(fencer: TrackedFencer) -> FencerStatus:
    """Return display metadata for the tracked fencer's status."""
    if not fencer.active:
        return FencerStatus("Disabled", "tag", "Tracking paused by user")

    if (
        fencer.failure_count >= fencer_scraper_service.FENCER_MAX_FAILURES
        and fencer.last_failure_at
    ):
        cooldown_expires = fencer.last_failure_at + timedelta(
            minutes=fencer_scraper_service.FENCER_FAILURE_COOLDOWN_MIN
        )
        if cooldown_expires > datetime.now(UTC):
            remaining = cooldown_expires - datetime.now(UTC)
            minutes = max(1, int(remaining.total_seconds() // 60))
            msg = (
                f"Cooling down after repeated failures. Next retry in about {minutes} minute(s)."
            )
            return FencerStatus("Cooling Down", "tag warning", msg)

    return FencerStatus("Active", "tag success", "Tracking normally")


def _format_timestamp(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _serialize_fencer(fencer: TrackedFencer) -> Dict[str, Any]:
    status = _determine_status(fencer)
    weapon_list = (fencer.weapon_filter.split(",") if fencer.weapon_filter else [])

    return {
        "id": fencer.id,
        "fencer_id": fencer.fencer_id,
        "display_name": fencer.display_name or f"Fencer {fencer.fencer_id}",
        "raw_display_name": fencer.display_name or "",
        "weapon_filter": fencer.weapon_filter,
        "weapon_list": weapon_list,
        "status_label": status.label,
        "status_css": status.css,
        "status_description": status.description,
        "active": fencer.active,
        "last_checked": _format_timestamp(fencer.last_checked_at),
        "last_failure": _format_timestamp(fencer.last_failure_at),
        "failure_count": fencer.failure_count,
        "profile_url": build_fencer_profile_url(fencer.fencer_id, fencer.display_name),
    }


def _build_context(
    db: Session,
    user: User,
    error: Optional[str] = None,
    success: Optional[str] = None,
) -> Dict[str, Any]:
    fencers = crud.get_all_tracked_fencers_for_user(db, user.id, active_only=False)
    active: List[Dict[str, Any]] = []
    inactive: List[Dict[str, Any]] = []

    for fencer in fencers:
        serialized = _serialize_fencer(fencer)
        if fencer.active:
            active.append(serialized)
        else:
            inactive.append(serialized)

    context: Dict[str, Any] = {
        "active_fencers": active,
        "inactive_fencers": inactive,
        "weapon_options": ALLOWED_WEAPONS,
    }

    if error:
        context["error"] = error
    if success:
        context["success"] = success

    return context


def build_fencer_management_context(db: Session, user: User) -> Dict[str, Any]:
    """Expose fencer context for other views (e.g., dashboard cards)."""
    return _build_context(db, user)


def _handle_weapon_filter(raw_value: str) -> Optional[str]:
    normalized = fencer_validation_service.normalize_weapon_filter(raw_value)
    if raw_value and not normalized:
        raise ValueError("Weapon filter must only include foil, epee, or saber")
    return normalized


@router.get("/fencers", response_class=HTMLResponse)
def list_tracked_fencers(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = request.query_params.get("success")
    error = request.query_params.get("error")

    return templates.TemplateResponse(
        "tracked_fencers.html",
        {
            "request": request,
            "user": user,
            **_build_context(db, user, error=error, success=success),
        },
    )


@router.post("/fencers")
async def create_tracked_fencer(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    form = await request.form()
    fencer_id_input = (form.get("fencer_id") or "").strip()
    weapon_filter_raw = (form.get("weapon_filter") or "").strip()

    # Extract fencer ID and slug from URL
    normalized_fencer_id, error_msg = fencer_validation_service.normalize_tracked_fencer_id(
        fencer_id_input
    )
    if error_msg:
        return templates.TemplateResponse(
            "tracked_fencers.html",
            {
                "request": request,
                "user": user,
                **_build_context(db, user, error=error_msg),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    fencer_id = normalized_fencer_id or ""

    # Extract display name from URL slug
    slug = fencer_validation_service.extract_profile_slug(fencer_id_input)
    display_name = fencer_validation_service.derive_display_name_from_slug(slug)

    try:
        weapon_filter = _handle_weapon_filter(weapon_filter_raw)
    except ValueError as exc:
        return templates.TemplateResponse(
            "tracked_fencers.html",
            {
                "request": request,
                "user": user,
                **_build_context(db, user, error=str(exc)),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existing = crud.get_tracked_fencer_for_user(db, user.id, fencer_id)
    if existing:
        if existing.active:
            return templates.TemplateResponse(
                "tracked_fencers.html",
                {
                    "request": request,
                    "user": user,
                    **_build_context(db, user, error="Fencer already tracked"),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Reactivate existing entry
        existing.active = True
        existing.failure_count = 0
        existing.last_failure_at = None
        existing.last_checked_at = None
        crud.update_tracked_fencer(
            db, existing, display_name=display_name, weapon_filter=weapon_filter
        )
        db.commit()
        return RedirectResponse(
            url="/fencers?success=Fencer%20re-activated",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Fallback: try to get name from cache or scrape if slug didn't provide a name
    if not display_name:
        cached_fencer = crud.get_fencer_by_fencingtracker_id(db, fencer_id)
        if cached_fencer and cached_fencer.name:
            display_name = cached_fencer.name
        else:
            display_name = fencer_scraper_service.fetch_fencer_display_name(fencer_id)

    final_display_name = display_name

    try:
        crud.create_tracked_fencer(
            db,
            user_id=user.id,
            fencer_id=fencer_id,
            display_name=final_display_name,
            weapon_filter=weapon_filter,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "tracked_fencers.html",
            {
                "request": request,
                "user": user,
                **_build_context(db, user, error="Fencer already tracked"),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url="/fencers?success=Fencer%20tracked%20successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/fencers/{tracked_fencer_id}/edit")
async def edit_tracked_fencer(
    tracked_fencer_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    fencer = crud.get_tracked_fencer_by_id(db, tracked_fencer_id)
    if not fencer or fencer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked fencer not found")

    form = await request.form()
    display_name = (form.get("display_name") or "").strip() or None
    weapon_filter_raw = (form.get("weapon_filter") or "").strip()

    try:
        weapon_filter = _handle_weapon_filter(weapon_filter_raw)
    except ValueError as exc:
        return templates.TemplateResponse(
            "tracked_fencers.html",
            {
                "request": request,
                "user": user,
                **_build_context(db, user, error=str(exc)),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    crud.update_tracked_fencer(
        db,
        fencer,
        display_name=display_name,
        weapon_filter=weapon_filter,
    )
    db.commit()

    return RedirectResponse(
        url="/fencers?success=Fencer%20updated",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/fencers/{tracked_fencer_id}/delete")
async def delete_tracked_fencer(
    tracked_fencer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    fencer = crud.get_tracked_fencer_by_id(db, tracked_fencer_id)
    if not fencer or fencer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked fencer not found")

    # Permanently delete the fencer
    db.delete(fencer)
    db.commit()

    return RedirectResponse(
        url="/fencers?success=Fencer%20deleted",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/fencers/{tracked_fencer_id}/deactivate")
async def deactivate_tracked_fencer(
    tracked_fencer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    fencer = crud.get_tracked_fencer_by_id(db, tracked_fencer_id)
    if not fencer or fencer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked fencer not found")

    crud.deactivate_tracked_fencer(db, fencer)
    db.commit()

    return RedirectResponse(
        url="/fencers?success=Fencer%20deactivated",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/fencers/{tracked_fencer_id}/reactivate")
async def reactivate_tracked_fencer(
    tracked_fencer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    fencer = crud.get_tracked_fencer_by_id(db, tracked_fencer_id)
    if not fencer or fencer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked fencer not found")

    fencer.active = True
    fencer.failure_count = 0
    fencer.last_failure_at = None
    fencer.last_checked_at = None
    db.commit()

    return RedirectResponse(
        url="/fencers?success=Fencer%20reactivated",
        status_code=status.HTTP_303_SEE_OTHER,
    )
