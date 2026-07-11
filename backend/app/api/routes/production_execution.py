from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, StockBalance
from app.models.production import ProductionBatch, Recipe
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event
from app.services.inventory import InventoryError, post_document

router = APIRouter(tags=["production-execution"])


def fail(status: int, message: str):
    raise HTTPException(status, message)


def utcnow():
    return datetime.now(timezone.utc)


def load_recipe(db: Session, recipe_id: str) -> Recipe | None:
    return db.scalar(select(Recipe).where(Recipe.id == recipe_id).options(selectinload(Recipe.lines)))


def load_batch(db: Session, batch_id: str, *, lock: bool = False) -> ProductionBatch | None:
    stmt = select(ProductionBatch).where(ProductionBatch.id == batch_id)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def item_cost(db: Session, item_id: str, location_id: str) -> Decimal:
    balance = db.scalar(select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id))
    if balance:
        return Decimal(balance.average_cost)
    item = db.get(Item, item_id)
    return Decimal(item.standard_cost if item else 0)


class MaterialActual(BaseModel):
    item_id: str
    actual_quantity: Decimal = Field(gt=0)


class ExecuteProduction(BaseModel):
    actual_output_quantity: Decimal = Field(gt=0)
    output_waste_quantity: Decimal = Field(default=0, ge=0)
    materials: list[MaterialActual] = Field(default_factory=list)
    notes: str | None = None


def execution_snapshot(db: Session, batch: ProductionBatch) -> dict:
    recipe = load_recipe(db, batch.recipe_id)
    if not recipe:
        fail(409, "Batch recipe is unavailable")
    factor = Decimal(batch.planned_quantity) / Decimal(recipe.yield_quantity)
    materials = []
    total_planned_cost = Decimal("0")
    for line in recipe.lines:
        planned = Decimal(line.quantity) * factor * (Decimal("1") + Decimal(line.waste_factor))
        cost = item_cost(db, line.ingredient_item_id, batch.location_id)
        total_planned_cost += planned * cost
        materials.append({
            "item_id": line.ingredient_item_id,
            "planned_quantity": planned,
            "unit_cost": cost,
            "planned_cost": planned * cost,
            "optional": line.optional,
        })
    return {
        "batch": {
            "id": batch.id,
            "batch_number": batch.batch_number,
            "recipe_id": batch.recipe_id,
            "location_id": batch.location_id,
            "planned_quantity": batch.planned_quantity,
            "actual_quantity": batch.actual_quantity,
            "status": batch.status,
            "notes": batch.notes,
            "stock_document_id": batch.stock_document_id,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
        },
        "recipe": {
            "id": recipe.id,
            "code": recipe.code,
            "name": recipe.name,
            "version": recipe.version,
            "output_item_id": recipe.output_item_id,
            "yield_quantity": recipe.yield_quantity,
        },
        "materials": materials,
        "planned_total_cost": total_planned_cost,
        "planned_cost_per_output_unit": total_planned_cost / Decimal(batch.planned_quantity),
    }


@router.get("/production-batches/{batch_id}/execution-detail")
def get_execution_detail(batch_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.read"))):
    batch = load_batch(db, batch_id)
    if not batch:
        fail(404, "Production batch not found")
    return execution_snapshot(db, batch)


@router.post("/production-batches/{batch_id}/start")
def start_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    batch = load_batch(db, batch_id, lock=True)
    if not batch:
        fail(404, "Production batch not found")
    if batch.status != "planned":
        fail(409, "Only planned batches can be started")
    recipe = load_recipe(db, batch.recipe_id)
    if not recipe or recipe.status != "approved":
        fail(409, "The approved recipe version is no longer available")
    batch.status = "in_progress"
    add_audit(db, actor_user_id=user.id, action="production.started", entity_type="production_batch", entity_id=batch.id, details={"batch_number": batch.batch_number})
    db.commit()
    return execution_snapshot(db, batch)


@router.post("/production-batches/{batch_id}/execute")
def execute_batch(batch_id: str, payload: ExecuteProduction, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    batch = load_batch(db, batch_id, lock=True)
    if not batch:
        fail(404, "Production batch not found")
    if batch.status != "in_progress":
        fail(409, "Only in-progress batches can be completed")
    recipe = load_recipe(db, batch.recipe_id)
    if not recipe:
        fail(409, "Batch recipe is unavailable")

    supplied = {line.item_id: Decimal(line.actual_quantity) for line in payload.materials}
    if len(supplied) != len(payload.materials):
        fail(422, "Actual material lines must be unique")
    recipe_ids = {line.ingredient_item_id for line in recipe.lines}
    unknown = set(supplied) - recipe_ids
    if unknown:
        fail(422, "Actual materials must belong to the batch recipe")

    planned_factor = Decimal(batch.planned_quantity) / Decimal(recipe.yield_quantity)
    entries = []
    variances = []
    total_actual_cost = Decimal("0")
    for line in recipe.lines:
        planned_quantity = Decimal(line.quantity) * planned_factor * (Decimal("1") + Decimal(line.waste_factor))
        actual_quantity = supplied.get(line.ingredient_item_id, planned_quantity)
        if not line.optional and actual_quantity <= 0:
            fail(422, "Required recipe materials must have a positive actual quantity")
        cost = item_cost(db, line.ingredient_item_id, batch.location_id)
        actual_cost = actual_quantity * cost
        total_actual_cost += actual_cost
        entries.append({"item_id": line.ingredient_item_id, "location_id": batch.location_id, "quantity": -actual_quantity, "unit_cost": cost, "reason": "production actual consumption"})
        variances.append({
            "item_id": line.ingredient_item_id,
            "planned_quantity": str(planned_quantity),
            "actual_quantity": str(actual_quantity),
            "quantity_variance": str(actual_quantity - planned_quantity),
            "unit_cost": str(cost),
            "actual_cost": str(actual_cost),
        })

    good_output = Decimal(payload.actual_output_quantity)
    output_waste = Decimal(payload.output_waste_quantity)
    if output_waste > good_output:
        fail(422, "Output waste cannot exceed actual output")
    entries.append({
        "item_id": recipe.output_item_id,
        "location_id": batch.location_id,
        "quantity": good_output,
        "unit_cost": total_actual_cost / good_output,
        "reason": "production output",
    })

    yield_variance = good_output - Decimal(batch.planned_quantity)
    try:
        document = post_document(
            db,
            kind="production",
            actor_id=user.id,
            entries=entries,
            reference=batch.batch_number,
            notes=payload.notes or batch.notes,
            idempotency_key=f"production-execution:{batch.id}",
            commit=False,
        )
        batch.actual_quantity = good_output
        batch.status = "completed"
        batch.completed_by_user_id = user.id
        batch.completed_at = utcnow()
        batch.stock_document_id = document.id
        details = {
            "actual_output_quantity": str(good_output),
            "output_waste_quantity": str(output_waste),
            "yield_variance": str(yield_variance),
            "total_actual_cost": str(total_actual_cost),
            "cost_per_output_unit": str(total_actual_cost / good_output),
            "materials": variances,
        }
        add_audit(db, actor_user_id=user.id, action="production.executed", entity_type="production_batch", entity_id=batch.id, details=details)
        enqueue_event(
            db,
            destination_system="accounting",
            event_type="inventory.production.executed",
            aggregate_type="production_batch",
            aggregate_id=batch.id,
            idempotency_key=f"production-executed:{batch.id}",
            payload={"batch_id": batch.id, "batch_number": batch.batch_number, "stock_document_id": document.id, **details},
        )
        if yield_variance < 0 or output_waste > 0:
            add_notification(db, user_id=user.id, title="Production variance recorded", body=f"{batch.batch_number} completed with yield variance {yield_variance} and waste {output_waste}.", severity="warning")
        db.commit()
        return {"execution": execution_snapshot(db, batch), "variance": details}
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.post("/production-batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    batch = load_batch(db, batch_id, lock=True)
    if not batch:
        fail(404, "Production batch not found")
    if batch.status not in {"planned", "in_progress"}:
        fail(409, "Only open batches can be cancelled")
    previous = batch.status
    batch.status = "cancelled"
    add_audit(db, actor_user_id=user.id, action="production.cancelled", entity_type="production_batch", entity_id=batch.id, details={"previous_status": previous})
    db.commit()
    return execution_snapshot(db, batch)
