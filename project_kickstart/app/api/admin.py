"""Admin routes."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import User

from .dependencies import get_current_user, require_admin, templates, validate_csrf


router = APIRouter(prefix="/admin")


def _serialize_user(user: User, tracked_club_count: int) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "tracked_club_count": tracked_club_count,
    }


@router.get("/users", response_class=HTMLResponse)
def list_users(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    counts = {row["user_id"]: row["tracked_club_count"] for row in crud.get_registration_counts_for_users(db)}
    serialized = [_serialize_user(user, counts.get(user.id, 0)) for user in users]

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": admin,
            "users": serialized,
        },
    )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _csrf: None = Depends(validate_csrf),
):
    payload = await request.json()
    updates: Dict[str, Any] = {}

    if "is_admin" in payload:
        updates["is_admin"] = bool(payload["is_admin"])
    if "is_active" in payload:
        updates["is_active"] = bool(payload["is_active"])

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    if user_id == admin.id and "is_active" in updates and not updates["is_active"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    try:
        user = crud.update_user(db, user_id, **updates)
        db.commit()
    except ValueError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    counts = {row["user_id"]: row["tracked_club_count"] for row in crud.get_registration_counts_for_users(db)}
    return JSONResponse(_serialize_user(user, counts.get(user.id, 0)))
