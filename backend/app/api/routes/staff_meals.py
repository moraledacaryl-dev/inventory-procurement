from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.staff_meals import StaffMeal
from app.models.user import User
from app.schemas.staff_meals import StaffMealCreate, StaffMealOut, StaffMealPreview
from app.services.staff_meals import StaffMealError, post_staff_meal, preview_staff_meal, reverse_staff_meal


router = APIRouter(prefix="/staff-meals", tags=["staff meals"])


def conflict(exc: Exception):
    raise HTTPException(status_code=409, detail=str(exc))


@router.get("", response_model=list[StaffMealOut])
def list_staff_meals(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    return db.scalars(
        select(StaffMeal)
        .options(selectinload(StaffMeal.lines))
        .order_by(StaffMeal.created_at.desc())
        .limit(limit)
    ).all()


@router.get("/{meal_id}", response_model=StaffMealOut)
def get_staff_meal(
    meal_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    meal = db.scalar(
        select(StaffMeal).options(selectinload(StaffMeal.lines)).where(StaffMeal.id == meal_id)
    )
    if not meal:
        raise HTTPException(404, "Staff meal not found")
    return meal


@router.post("/preview", response_model=StaffMealPreview)
def preview(
    payload: StaffMealCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    try:
        return preview_staff_meal(
            db,
            location_id=payload.location_id,
            servings=payload.servings,
            lines=payload.lines,
        )
    except StaffMealError as exc:
        conflict(exc)


@router.post("", response_model=StaffMealOut, status_code=201)
def create_staff_meal(
    payload: StaffMealCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    try:
        return post_staff_meal(db, payload=payload, actor_id=user.id)
    except StaffMealError as exc:
        conflict(exc)


@router.post("/{meal_id}/reverse", response_model=StaffMealOut)
def reverse(
    meal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    try:
        return reverse_staff_meal(db, meal_id=meal_id, actor_id=user.id)
    except StaffMealError as exc:
        conflict(exc)
