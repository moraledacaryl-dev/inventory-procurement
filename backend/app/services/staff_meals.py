from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import Item, Location, StockBalance, StockDocument, StockMovement
from app.models.staff_meals import StaffMeal, StaffMealLine
from app.services.controls import add_audit
from app.services.inventory import InventoryError, post_document


class StaffMealError(ValueError):
    pass


def _validate_location(db: Session, location_id: str) -> Location:
    location = db.get(Location, location_id)
    if not location or not location.is_active:
        raise StaffMealError("Invalid or inactive location")
    return location


def _validate_lines(db: Session, location_id: str, lines):
    _validate_location(db, location_id)
    seen: set[str] = set()
    rows = []
    total = Decimal("0")
    for line in lines:
        if line.item_id in seen:
            raise StaffMealError("Each ingredient may appear only once")
        seen.add(line.item_id)
        item = db.get(Item, line.item_id)
        if not item or not item.is_active or not item.track_stock:
            raise StaffMealError("Invalid or inactive stock ingredient")
        quantity = Decimal(line.quantity)
        balance = db.scalar(
            select(StockBalance).where(
                StockBalance.item_id == item.id,
                StockBalance.location_id == location_id,
            )
        )
        available = Decimal(balance.quantity) if balance else Decimal("0")
        unit_cost = Decimal(balance.average_cost) if balance else Decimal(item.standard_cost or 0)
        if available < quantity and not item.allow_negative_stock:
            raise StaffMealError(f"Insufficient stock for {item.sku} at location")
        line_cost = quantity * unit_cost
        total += line_cost
        rows.append(
            {
                "item_id": item.id,
                "sku": item.sku,
                "item_name": item.name,
                "quantity": quantity,
                "available_quantity": available,
                "unit_cost": unit_cost,
                "line_cost": line_cost,
            }
        )
    return rows, total


def preview_staff_meal(db: Session, *, location_id: str, servings: int, lines):
    rows, total = _validate_lines(db, location_id, lines)
    return {
        "servings": servings,
        "total_cost": total,
        "cost_per_serving": total / Decimal(servings),
        "lines": rows,
    }


def post_staff_meal(db: Session, *, payload, actor_id: str) -> StaffMeal:
    _validate_lines(db, payload.location_id, payload.lines)
    entries = [
        {
            "item_id": line.item_id,
            "location_id": payload.location_id,
            "quantity": -Decimal(line.quantity),
            "unit_cost": Decimal("0"),
            "reason": f"staff meal: {payload.meal_name.strip()}",
        }
        for line in payload.lines
    ]
    key = f"staff-meal:{payload.idempotency_key}" if payload.idempotency_key else None
    try:
        document = post_document(
            db,
            kind="staff_meal",
            actor_id=actor_id,
            entries=entries,
            reference=payload.meal_name.strip(),
            notes=payload.notes,
            idempotency_key=key,
            commit=False,
        )
        existing = db.scalar(
            select(StaffMeal)
            .options(selectinload(StaffMeal.lines))
            .where(StaffMeal.posted_document_id == document.id)
        )
        if existing:
            db.commit()
            return existing

        movements = db.scalars(
            select(StockMovement)
            .where(StockMovement.document_id == document.id)
            .order_by(StockMovement.line_number)
        ).all()
        meal = StaffMeal(
            meal_number=document.document_number,
            meal_name=payload.meal_name.strip(),
            meal_period=payload.meal_period.strip() if payload.meal_period else None,
            servings=payload.servings,
            location_id=payload.location_id,
            notes=payload.notes,
            status="posted",
            posted_document_id=document.id,
            created_by_user_id=actor_id,
        )
        db.add(meal)
        db.flush()
        for movement in movements:
            meal.lines.append(
                StaffMealLine(
                    line_number=movement.line_number,
                    item_id=movement.item_id,
                    quantity=-Decimal(movement.quantity),
                    unit_cost=Decimal(movement.unit_cost),
                )
            )
        add_audit(
            db,
            actor_user_id=actor_id,
            action="staff_meal.posted",
            entity_type="staff_meal",
            entity_id=meal.id,
            details={
                "meal_number": meal.meal_number,
                "meal_name": meal.meal_name,
                "servings": meal.servings,
                "location_id": meal.location_id,
                "line_count": len(meal.lines),
            },
        )
        db.commit()
        return db.scalar(
            select(StaffMeal).options(selectinload(StaffMeal.lines)).where(StaffMeal.id == meal.id)
        )
    except (InventoryError, StaffMealError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if key:
            existing_doc = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == key))
            if existing_doc:
                existing = db.scalar(
                    select(StaffMeal)
                    .options(selectinload(StaffMeal.lines))
                    .where(StaffMeal.posted_document_id == existing_doc.id)
                )
                if existing:
                    return existing
        raise StaffMealError("Staff meal could not be posted") from exc


def reverse_staff_meal(db: Session, *, meal_id: str, actor_id: str) -> StaffMeal:
    meal = db.scalar(
        select(StaffMeal)
        .options(selectinload(StaffMeal.lines))
        .where(StaffMeal.id == meal_id)
        .with_for_update()
    )
    if not meal:
        raise StaffMealError("Staff meal not found")
    if meal.status == "reversed":
        return meal
    if meal.status != "posted":
        raise StaffMealError("Only posted staff meals can be reversed")

    original = db.get(StockDocument, meal.posted_document_id)
    if not original:
        raise StaffMealError("Original stock document is missing")
    entries = [
        {
            "item_id": line.item_id,
            "location_id": meal.location_id,
            "quantity": Decimal(line.quantity),
            "unit_cost": Decimal(line.unit_cost),
            "reason": f"staff meal reversal: {meal.meal_name}",
        }
        for line in meal.lines
    ]
    try:
        reversal = post_document(
            db,
            kind="staff_meal_reversal",
            actor_id=actor_id,
            entries=entries,
            reference=meal.meal_number,
            notes=f"Reversal of {meal.meal_number}",
            idempotency_key=f"staff-meal-reversal:{meal.id}",
            commit=False,
        )
        original.status = "reversed"
        original.reversed_document_id = reversal.id
        meal.status = "reversed"
        meal.reversal_document_id = reversal.id
        meal.reversed_by_user_id = actor_id
        meal.reversed_at = datetime.now(timezone.utc)
        add_audit(
            db,
            actor_user_id=actor_id,
            action="staff_meal.reversed",
            entity_type="staff_meal",
            entity_id=meal.id,
            details={"meal_number": meal.meal_number, "reversal_document_id": reversal.id},
        )
        db.commit()
        return db.scalar(
            select(StaffMeal).options(selectinload(StaffMeal.lines)).where(StaffMeal.id == meal.id)
        )
    except InventoryError as exc:
        db.rollback()
        raise StaffMealError(str(exc)) from exc
